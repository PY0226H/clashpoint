#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
SCRIPT="$ROOT/scripts/harness/ai_judge_ops_read_model_export.sh"

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

# 场景1：导出成功
WORK_OK="$TMP_DIR/ok"
mkdir -p "$WORK_OK/docs/loadtest/evidence" "$WORK_OK/docs/dev_plan" "$WORK_OK/artifacts/harness"

MOCK_BIN_OK="$TMP_DIR/mock-bin-ok"
mkdir -p "$MOCK_BIN_OK"
cat >"$MOCK_BIN_OK/curl" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
output_file=""
request_url=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    -o)
      output_file="${2:-}"
      shift 2
      ;;
    *)
      request_url="$1"
      shift 1
      ;;
  esac
done
if [[ -n "$output_file" ]]; then
  if [[ "$request_url" == *"/internal/judge/ops/read-model/pack"* ]]; then
    cat >"$output_file" <<'JSON'
{
  "generatedAt": "2026-04-17T09:00:00Z",
  "fairnessDashboard": {
    "overview": {
      "totalMatched": 15,
      "scannedCases": 12,
      "scanTruncated": true,
      "reviewRequiredCount": 4,
      "openReviewCount": 2,
      "panelHighDisagreementCount": 1,
      "driftBreachCount": 1,
      "thresholdBreachCount": 1,
      "shadowBreachCount": 1
    },
    "gateDistribution": {
      "auto_passed": 9,
      "review_required": 2,
      "benchmark_attention_required": 1,
      "unknown": 0
    },
    "trends": {
      "windowDays": 7,
      "caseDaily": [],
      "benchmarkRuns": [],
      "shadowRuns": []
    },
    "topRiskCases": [],
    "filters": {"windowDays": 7}
  },
  "fairnessCalibrationAdvisor": {
    "overview": {"highRiskCount": 4}
  },
  "panelRuntimeReadiness": {
    "overview": {"attentionGroupCount": 2}
  },
  "registryGovernance": {
    "dependencyHealth": {"invalidCount": 2}
  },
  "registryPromptToolGovernance": {
    "riskSummary": {"total": 3, "high": 1},
    "riskItems": [{"severity": "high"}]
  },
  "courtroomReadModel": {
    "count": 3,
    "items": [{"caseId": 901}]
  },
  "courtroomQueue": {
    "count": 4,
    "items": [{"caseId": 901}]
  },
  "courtroomDrilldown": {
    "count": 4,
    "aggregations": {
      "highRiskCount": 2,
      "reviewRequiredCount": 3,
      "totalConflictPairCount": 5,
      "totalUnansweredClaimCount": 4,
      "totalDecisiveEvidenceCount": 6,
      "totalPivotalMomentCount": 7
    },
    "items": [{"caseId": 901}]
  },
  "reviewQueue": {
    "count": 6,
    "items": [{"workflow": {"caseId": 901}}]
  },
  "reviewTrustPriority": {
    "count": 5,
    "items": [{"workflow": {"caseId": 901}}]
  },
  "evidenceClaimQueue": {
    "count": 6,
    "aggregations": {
      "riskLevelCounts": {"high": 2, "medium": 1, "low": 3},
      "reliabilityLevelCounts": {"high": 2, "medium": 2, "low": 1, "unknown": 1},
      "conflictCaseCount": 3,
      "unansweredCaseCount": 2
    },
    "items": [{"workflow": {"caseId": 901}}]
  },
  "trustChallengeQueue": {
    "count": 3,
    "items": [{"caseId": 901}]
  },
  "policyGateSimulation": {
    "summary": {"blockedCount": 2},
    "items": [{"simulatedGate": {"status": "blocked"}}]
  },
  "adaptiveSummary": {
    "recommendedActionCount": 5,
    "panelAttentionGroupCount": 2,
    "calibrationHighRiskCount": 4,
    "courtroomSampleCount": 3,
    "courtroomQueueCount": 4,
    "reviewQueueCount": 6,
    "reviewHighRiskCount": 2,
    "reviewTrustPriorityCount": 5,
    "reviewUnifiedHighPriorityCount": 3,
    "trustChallengeQueueCount": 3,
    "trustChallengeHighPriorityCount": 2,
    "policySimulationBlockedCount": 2,
    "registryPromptToolRiskCount": 3,
    "registryPromptToolHighRiskCount": 1,
    "evidenceClaimQueueCount": 6,
    "evidenceClaimHighRiskCount": 2,
    "evidenceClaimConflictCaseCount": 3,
    "evidenceClaimUnansweredClaimCaseCount": 2,
    "courtroomDrilldownCount": 4,
    "courtroomDrilldownHighRiskCount": 2,
    "courtroomDrilldownReviewRequiredCount": 3
  },
  "trustOverview": {
    "count": 2,
    "errorCount": 1,
    "items": [
      {"caseId": 901, "verdictVerified": true},
      {"caseId": 902, "verdictVerified": false}
    ]
  },
  "filters": {
    "dispatchType": "final"
  }
}
JSON
  elif [[ "$request_url" == *"/internal/judge/fairness/cases"* ]]; then
    cat >"$output_file" <<'JSON'
{
  "count": 15,
  "returned": 12,
  "items": [],
  "aggregations": {
    "totalMatched": 15,
    "reviewRequiredCount": 4,
    "openReviewCount": 2,
    "driftBreachCount": 1,
    "thresholdBreachCount": 1,
    "shadowBreachCount": 1,
    "panelHighDisagreementCount": 1,
    "withChallengeCount": 2,
    "gateConclusionCounts": {
      "auto_passed": 9,
      "review_required": 2,
      "benchmark_attention_required": 3,
      "unknown": 1
    },
    "winnerCounts": {
      "pro": 7,
      "con": 5,
      "draw": 2,
      "unknown": 1
    },
    "challengeStateCounts": {
      "none": 13,
      "under_review": 2
    },
    "policyVersionCounts": {
      "v3-default": 15,
      "unknown": 0
    }
  },
  "filters": {
    "status": null,
    "dispatchType": "final",
    "winner": null,
    "policyVersion": "v3-default",
    "hasDriftBreach": null,
    "hasThresholdBreach": null,
    "hasShadowBreach": null,
    "hasOpenReview": null,
    "gateConclusion": null,
    "challengeState": null,
    "sortBy": "updated_at",
    "sortOrder": "desc",
    "reviewRequired": null,
    "panelHighDisagreement": null,
    "offset": 0,
    "limit": 200
  }
}
JSON
  elif [[ "$request_url" == *"/internal/judge/panels/runtime/profiles"* ]]; then
    cat >"$output_file" <<'JSON'
{
  "count": 30,
  "returned": 30,
  "items": [],
  "aggregations": {
    "totalMatched": 30,
    "reviewRequiredCount": 4,
    "openReviewCount": 3,
    "panelHighDisagreementCount": 2,
    "avgPanelDisagreementRatio": 0.11,
    "byJudgeId": {"judgeA": 10, "judgeB": 10, "judgeC": 10},
    "byProfileId": {"panel-judgeA-weighted-v1": 10, "panel-judgeB-weighted-v1": 10, "panel-judgeC-weighted-v1": 10, "unknown": 0},
    "byModelStrategy": {"deterministic_path_alignment": 30, "unknown": 0},
    "byStrategySlot": {"path_alignment": 30, "unknown": 0},
    "byDomainSlot": {"general": 30, "unknown": 0},
    "byProfileSource": {"builtin_default": 30, "unknown": 0},
    "byPolicyVersion": {"v3-default": 30, "unknown": 0},
    "winnerCounts": {"pro": 12, "con": 10, "draw": 8, "unknown": 0}
  },
  "filters": {
    "status": null,
    "dispatchType": "final",
    "winner": null,
    "policyVersion": "v3-default",
    "hasOpenReview": null,
    "gateConclusion": null,
    "challengeState": null,
    "reviewRequired": null,
    "panelHighDisagreement": null,
    "judgeId": null,
    "profileSource": null,
    "profileId": null,
    "modelStrategy": null,
    "strategySlot": null,
    "domainSlot": null,
    "sortBy": "updated_at",
    "sortOrder": "desc",
    "offset": 0,
    "limit": 200
  }
}
JSON
  elif [[ "$request_url" == *"/internal/judge/trust/challenges/ops-queue"* ]]; then
    cat >"$output_file" <<'JSON'
{
  "count": 5,
  "returned": 2,
  "scanned": 12,
  "skipped": 7,
  "errorCount": 1,
  "items": [
    {"caseId": 901},
    {"caseId": 902}
  ],
  "errors": [
    {"caseId": 903, "statusCode": 404, "errorCode": "trust_receipt_not_found"}
  ],
  "filters": {
    "status": null,
    "dispatchType": "final",
    "challengeState": "open",
    "reviewState": null,
    "priorityLevel": null,
    "slaBucket": null,
    "hasOpenAlert": null,
    "sortBy": "priority_score",
    "sortOrder": "desc",
    "scanLimit": 500,
    "offset": 0,
    "limit": 10
  }
}
JSON
  elif [[ "$request_url" == *"/internal/judge/cases/901/trust/public-verify"* ]]; then
    cat >"$output_file" <<'JSON'
{
  "caseId": 901,
  "dispatchType": "final",
  "traceId": "trace-final-901",
  "verifyPayload": {
    "caseCommitment": {
      "version": "trust-phaseA-case-commitment-v1",
      "commitmentHash": "sha256:commitment-hash-901"
    },
    "verdictAttestation": {
      "version": "trust-phaseA-verdict-attestation-v1",
      "registryHash": "sha256:verdict-registry-hash-901",
      "verified": true,
      "mismatchComponents": []
    },
    "challengeReview": {
      "version": "trust-phaseB-challenge-review-v1",
      "registryHash": "sha256:challenge-registry-hash-901"
    },
    "kernelVersion": {
      "version": "trust-phaseA-kernel-version-v1",
      "kernelHash": "sha256:kernel-hash-901"
    },
    "auditAnchor": {
      "version": "trust-phaseA-audit-anchor-v1",
      "anchorHash": "sha256:audit-anchor-hash-901"
    }
  }
}
JSON
  else
    cat >"$output_file" <<'JSON'
{}
JSON
  fi
fi
printf '200'
EOF
chmod +x "$MOCK_BIN_OK/curl"

OK_STDOUT="$TMP_DIR/ok.stdout"
OK_JSON_OUT="$TMP_DIR/ok.ops.json"
OK_MD_OUT="$TMP_DIR/ok.ops.md"
OK_ENV_OUT="$TMP_DIR/ok.ops.env"

PATH="$MOCK_BIN_OK:$PATH" bash "$SCRIPT" \
  --root "$WORK_OK" \
  --base-url "http://127.0.0.1:8787" \
  --internal-key "test-key" \
  --trust-public-verify-case-id 901 \
  --output-json "$OK_JSON_OUT" \
  --output-md "$OK_MD_OUT" \
  --output-env "$OK_ENV_OUT" >"$OK_STDOUT"

expect_contains "ok status stdout" "ai_judge_ops_read_model_export_status: pass" "$OK_STDOUT"
expect_contains "ok env status" "AI_JUDGE_OPS_READ_MODEL_EXPORT_STATUS=pass" "$OK_ENV_OUT"
expect_contains "ok env fairness matched" "OPS_READ_MODEL_FAIRNESS_TOTAL_MATCHED=15" "$OK_ENV_OUT"
expect_contains "ok env fairness scanned" "OPS_READ_MODEL_FAIRNESS_SCANNED_CASES=12" "$OK_ENV_OUT"
expect_contains "ok env fairness benchmark attention" "OPS_READ_MODEL_FAIRNESS_BENCHMARK_ATTENTION_COUNT=1" "$OK_ENV_OUT"
expect_contains "ok env case fairness matched" "OPS_READ_MODEL_CASE_FAIRNESS_TOTAL_MATCHED=15" "$OK_ENV_OUT"
expect_contains "ok env case fairness returned" "OPS_READ_MODEL_CASE_FAIRNESS_RETURNED=12" "$OK_ENV_OUT"
expect_contains "ok env panel runtime matched" "OPS_READ_MODEL_PANEL_RUNTIME_PROFILE_TOTAL_MATCHED=30" "$OK_ENV_OUT"
expect_contains "ok env panel runtime returned" "OPS_READ_MODEL_PANEL_RUNTIME_PROFILE_RETURNED=30" "$OK_ENV_OUT"
expect_contains "ok env trust queue matched" "OPS_READ_MODEL_TRUST_CHALLENGE_QUEUE_TOTAL_MATCHED=5" "$OK_ENV_OUT"
expect_contains "ok env trust queue returned" "OPS_READ_MODEL_TRUST_CHALLENGE_QUEUE_RETURNED=2" "$OK_ENV_OUT"
expect_contains "ok env trust queue error count" "OPS_READ_MODEL_TRUST_CHALLENGE_QUEUE_ERROR_COUNT=1" "$OK_ENV_OUT"
expect_contains "ok env trust public verify enabled" "OPS_READ_MODEL_TRUST_PUBLIC_VERIFY_ENABLED=1" "$OK_ENV_OUT"
expect_contains "ok env trust public verify case id" "OPS_READ_MODEL_TRUST_PUBLIC_VERIFY_CASE_ID=901" "$OK_ENV_OUT"
expect_contains "ok env trust public verify verified" "OPS_READ_MODEL_TRUST_PUBLIC_VERIFY_VERDICT_VERIFIED=1" "$OK_ENV_OUT"
expect_contains "ok env trust commitment hash present" "OPS_READ_MODEL_TRUST_PUBLIC_VERIFY_COMMITMENT_HASH_PRESENT=1" "$OK_ENV_OUT"
expect_contains "ok env trust verdict registry hash present" "OPS_READ_MODEL_TRUST_PUBLIC_VERIFY_VERDICT_REGISTRY_HASH_PRESENT=1" "$OK_ENV_OUT"
expect_contains "ok env trust challenge registry hash present" "OPS_READ_MODEL_TRUST_PUBLIC_VERIFY_CHALLENGE_REGISTRY_HASH_PRESENT=1" "$OK_ENV_OUT"
expect_contains "ok env invalid count" "OPS_READ_MODEL_REGISTRY_INVALID_COUNT=2" "$OK_ENV_OUT"
expect_contains "ok env trust item count" "OPS_READ_MODEL_TRUST_ITEM_COUNT=2" "$OK_ENV_OUT"
expect_contains "ok env adaptive action count" "OPS_READ_MODEL_ADAPTIVE_RECOMMENDED_ACTION_COUNT=5" "$OK_ENV_OUT"
expect_contains "ok env panel attention count" "OPS_READ_MODEL_ADAPTIVE_PANEL_ATTENTION_GROUP_COUNT=2" "$OK_ENV_OUT"
expect_contains "ok env calibration high risk" "OPS_READ_MODEL_ADAPTIVE_CALIBRATION_HIGH_RISK_COUNT=4" "$OK_ENV_OUT"
expect_contains "ok env courtroom sample count" "OPS_READ_MODEL_COURTROOM_SAMPLE_COUNT=3" "$OK_ENV_OUT"
expect_contains "ok env courtroom queue count" "OPS_READ_MODEL_COURTROOM_QUEUE_COUNT=4" "$OK_ENV_OUT"
expect_contains "ok env review queue count" "OPS_READ_MODEL_REVIEW_QUEUE_COUNT=6" "$OK_ENV_OUT"
expect_contains "ok env review high risk count" "OPS_READ_MODEL_REVIEW_HIGH_RISK_COUNT=2" "$OK_ENV_OUT"
expect_contains "ok env review trust priority count" "OPS_READ_MODEL_REVIEW_TRUST_PRIORITY_COUNT=5" "$OK_ENV_OUT"
expect_contains "ok env review unified high priority count" "OPS_READ_MODEL_REVIEW_UNIFIED_HIGH_PRIORITY_COUNT=3" "$OK_ENV_OUT"
expect_contains "ok env trust challenge queue count" "OPS_READ_MODEL_TRUST_CHALLENGE_QUEUE_COUNT=3" "$OK_ENV_OUT"
expect_contains "ok env trust challenge high priority count" "OPS_READ_MODEL_TRUST_CHALLENGE_HIGH_PRIORITY_COUNT=2" "$OK_ENV_OUT"
expect_contains "ok env policy sim blocked count" "OPS_READ_MODEL_POLICY_SIM_BLOCKED_COUNT=2" "$OK_ENV_OUT"
expect_contains "ok env registry prompt tool risk count" "OPS_READ_MODEL_REGISTRY_PROMPT_TOOL_RISK_COUNT=3" "$OK_ENV_OUT"
expect_contains "ok env registry prompt tool high risk count" "OPS_READ_MODEL_REGISTRY_PROMPT_TOOL_HIGH_RISK_COUNT=1" "$OK_ENV_OUT"
expect_contains "ok env evidence claim queue count" "OPS_READ_MODEL_EVIDENCE_CLAIM_QUEUE_COUNT=6" "$OK_ENV_OUT"
expect_contains "ok env evidence claim high risk count" "OPS_READ_MODEL_EVIDENCE_CLAIM_HIGH_RISK_COUNT=2" "$OK_ENV_OUT"
expect_contains "ok env evidence claim conflict case count" "OPS_READ_MODEL_EVIDENCE_CLAIM_CONFLICT_CASE_COUNT=3" "$OK_ENV_OUT"
expect_contains "ok env evidence claim unanswered case count" "OPS_READ_MODEL_EVIDENCE_CLAIM_UNANSWERED_CASE_COUNT=2" "$OK_ENV_OUT"
expect_contains "ok env courtroom drilldown count" "OPS_READ_MODEL_COURTROOM_DRILLDOWN_COUNT=4" "$OK_ENV_OUT"
expect_contains "ok env courtroom drilldown high risk count" "OPS_READ_MODEL_COURTROOM_DRILLDOWN_HIGH_RISK_COUNT=2" "$OK_ENV_OUT"
expect_contains "ok env courtroom drilldown review required count" "OPS_READ_MODEL_COURTROOM_DRILLDOWN_REVIEW_REQUIRED_COUNT=3" "$OK_ENV_OUT"
expect_contains "ok stdout case fairness http" "ops_case_fairness_http_code: 200" "$OK_STDOUT"
expect_contains "ok stdout panel profile http" "ops_panel_runtime_profile_http_code: 200" "$OK_STDOUT"
expect_contains "ok stdout trust queue http" "ops_trust_challenge_queue_http_code: 200" "$OK_STDOUT"
expect_contains "ok stdout trust public verify http" "ops_trust_public_verify_http_code: 200" "$OK_STDOUT"
expect_contains "ok md title" "# AI Judge Ops Read Model 导出快照" "$OK_MD_OUT"

# 场景2：trust public verify 缺少 challenge registry hash -> payload_invalid
WORK_TRUST_VERIFY_BAD="$TMP_DIR/trust-verify-bad"
mkdir -p "$WORK_TRUST_VERIFY_BAD/docs/loadtest/evidence" "$WORK_TRUST_VERIFY_BAD/docs/dev_plan" "$WORK_TRUST_VERIFY_BAD/artifacts/harness"

MOCK_BIN_TRUST_VERIFY_BAD="$TMP_DIR/mock-bin-trust-verify-bad"
mkdir -p "$MOCK_BIN_TRUST_VERIFY_BAD"
awk '!/challenge-registry-hash-901/' "$MOCK_BIN_OK/curl" >"$MOCK_BIN_TRUST_VERIFY_BAD/curl"
chmod +x "$MOCK_BIN_TRUST_VERIFY_BAD/curl"

TRUST_VERIFY_BAD_STDOUT="$TMP_DIR/trust-verify-bad.stdout"
TRUST_VERIFY_BAD_ENV_OUT="$TMP_DIR/trust-verify-bad.ops.env"
set +e
PATH="$MOCK_BIN_TRUST_VERIFY_BAD:$PATH" bash "$SCRIPT" \
  --root "$WORK_TRUST_VERIFY_BAD" \
  --base-url "http://127.0.0.1:8787" \
  --internal-key "test-key" \
  --trust-public-verify-case-id 901 \
  --output-env "$TRUST_VERIFY_BAD_ENV_OUT" >"$TRUST_VERIFY_BAD_STDOUT" 2>&1
TRUST_VERIFY_BAD_CODE="$?"
set -e
if [[ "$TRUST_VERIFY_BAD_CODE" -eq 0 ]]; then
  echo "[FAIL] trust verify missing registry hash should exit non-zero"
  cat "$TRUST_VERIFY_BAD_STDOUT"
  exit 1
fi
expect_contains "trust verify bad status stdout" "ai_judge_ops_read_model_export_status: payload_invalid" "$TRUST_VERIFY_BAD_STDOUT"
expect_contains "trust verify bad missing challenge hash key" "trustPublicVerify.challengeReview.registryHash" "$TRUST_VERIFY_BAD_STDOUT"
expect_contains "trust verify bad env status" "AI_JUDGE_OPS_READ_MODEL_EXPORT_STATUS=payload_invalid" "$TRUST_VERIFY_BAD_ENV_OUT"

# 场景3：payload 缺少必填键 -> payload_invalid
WORK_BAD="$TMP_DIR/bad"
mkdir -p "$WORK_BAD/docs/loadtest/evidence" "$WORK_BAD/docs/dev_plan" "$WORK_BAD/artifacts/harness"

MOCK_BIN_BAD="$TMP_DIR/mock-bin-bad"
mkdir -p "$MOCK_BIN_BAD"
cat >"$MOCK_BIN_BAD/curl" <<'EOF'
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
  cat >"$output_file" <<'JSON'
{"fairnessDashboard": {"overview": {"totalMatched": 3}}}
JSON
fi
printf '200'
EOF
chmod +x "$MOCK_BIN_BAD/curl"

BAD_STDOUT="$TMP_DIR/bad.stdout"
BAD_ENV_OUT="$TMP_DIR/bad.ops.env"
set +e
PATH="$MOCK_BIN_BAD:$PATH" bash "$SCRIPT" \
  --root "$WORK_BAD" \
  --base-url "http://127.0.0.1:8787" \
  --internal-key "test-key" \
  --output-env "$BAD_ENV_OUT" >"$BAD_STDOUT" 2>&1
BAD_CODE="$?"
set -e
if [[ "$BAD_CODE" -eq 0 ]]; then
  echo "[FAIL] payload invalid should exit non-zero"
  cat "$BAD_STDOUT"
  exit 1
fi
expect_contains "bad status stdout" "ai_judge_ops_read_model_export_status: payload_invalid" "$BAD_STDOUT"
expect_contains "bad missing keys stdout" "required_keys_missing:" "$BAD_STDOUT"
expect_contains "bad env status" "AI_JUDGE_OPS_READ_MODEL_EXPORT_STATUS=payload_invalid" "$BAD_ENV_OUT"

# 场景4：pack 顶层完整，但 fairnessDashboard 缺少冻结字段 -> payload_invalid
WORK_NESTED_BAD="$TMP_DIR/nested-bad"
mkdir -p "$WORK_NESTED_BAD/docs/loadtest/evidence" "$WORK_NESTED_BAD/docs/dev_plan" "$WORK_NESTED_BAD/artifacts/harness"

MOCK_BIN_NESTED_BAD="$TMP_DIR/mock-bin-nested-bad"
mkdir -p "$MOCK_BIN_NESTED_BAD"
cat >"$MOCK_BIN_NESTED_BAD/curl" <<'EOF'
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
  cat >"$output_file" <<'JSON'
{
  "generatedAt": "2026-04-17T09:00:00Z",
  "fairnessDashboard": {
    "overview": {"totalMatched": 3}
  },
  "fairnessCalibrationAdvisor": {},
  "panelRuntimeReadiness": {},
  "registryGovernance": {},
  "registryPromptToolGovernance": {},
  "courtroomReadModel": {},
  "courtroomQueue": {},
  "courtroomDrilldown": {},
  "reviewQueue": {},
  "reviewTrustPriority": {},
  "evidenceClaimQueue": {},
  "trustChallengeQueue": {},
  "policyGateSimulation": {},
  "adaptiveSummary": {},
  "trustOverview": {},
  "filters": {}
}
JSON
fi
printf '200'
EOF
chmod +x "$MOCK_BIN_NESTED_BAD/curl"

NESTED_BAD_STDOUT="$TMP_DIR/nested-bad.stdout"
NESTED_BAD_ENV_OUT="$TMP_DIR/nested-bad.ops.env"
set +e
PATH="$MOCK_BIN_NESTED_BAD:$PATH" bash "$SCRIPT" \
  --root "$WORK_NESTED_BAD" \
  --base-url "http://127.0.0.1:8787" \
  --internal-key "test-key" \
  --output-env "$NESTED_BAD_ENV_OUT" >"$NESTED_BAD_STDOUT" 2>&1
NESTED_BAD_CODE="$?"
set -e
if [[ "$NESTED_BAD_CODE" -eq 0 ]]; then
  echo "[FAIL] nested payload invalid should exit non-zero"
  cat "$NESTED_BAD_STDOUT"
  exit 1
fi
expect_contains "nested bad status stdout" "ai_judge_ops_read_model_export_status: payload_invalid" "$NESTED_BAD_STDOUT"
expect_contains "nested bad missing fairness key" "fairnessDashboard.gateDistribution" "$NESTED_BAD_STDOUT"
expect_contains "nested bad env status" "AI_JUDGE_OPS_READ_MODEL_EXPORT_STATUS=payload_invalid" "$NESTED_BAD_ENV_OUT"

echo "all ai-judge ops read model export tests passed"
