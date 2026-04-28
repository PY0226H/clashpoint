#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
SCRIPT="$ROOT/scripts/harness/ai_judge_stage_closure_evidence.sh"
DRAFT_SCRIPT="$ROOT/scripts/harness/ai_judge_stage_closure_draft.sh"

for path in "$SCRIPT" "$DRAFT_SCRIPT"; do
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

write_plan_doc_with_candidates() {
  local file="$1"
  cat >"$file" <<'EOF_PLAN'
# 当前开发计划

### 已完成/未完成矩阵
| 阶段 | 目标 | 状态 | 说明 |
| --- | --- | --- | --- |
| ai-judge-module-a | P1 | 进行中（phase 已完成） | done-a |
| ai-judge-module-b | P1 | 进行中 | doing-b |

## 5. 延后事项（不阻塞当前阶段）

1. 真实线上压测数据驱动的容量规划

### 下一开发模块建议

1. ai-judge-real-env-window-closure
EOF_PLAN
}

write_plan_doc_without_candidates() {
  local file="$1"
  cat >"$file" <<'EOF_PLAN'
# 当前开发计划

### 已完成/未完成矩阵
| 阶段 | 目标 | 状态 | 说明 |
| --- | --- | --- | --- |
| ai-judge-module-a | P1 | 进行中 | doing-a |

## 5. 延后事项（不阻塞当前阶段）

### 下一开发模块建议

1. ai-judge-doc-governance-refresh
EOF_PLAN
}

write_reset_plan_with_archive() {
  local file="$1"
  local archive_path="$2"
  cat >"$file" <<EOF_PLAN
# 当前开发计划

关联 slot：\`default\`
当前主线：\`AI_judge_service 下一阶段（待规划）\`
当前状态：阶段收口后待下一轮

## 1. 计划定位

1. 本轮完整执行细节已归档到：\`$archive_path\`。

### 已完成/未完成矩阵

| 阶段 | 目标 | 状态 | 说明 |
| --- | --- | --- | --- |
| \`ai-judge-stage-closure-execute\` | AI judge 当前阶段收口执行 | 已完成 | 活动计划已归档并重置，长期文档已同步 |
EOF_PLAN
}

write_long_term_docs() {
  local root="$1"
  mkdir -p "$root/docs/dev_plan"
  cat >"$root/docs/dev_plan/completed.md" <<'EOF_COMPLETED'
# completed

### B41. AI Judge 平台化重构阶段收口（来源：当前开发计划）
| 模块 | 结论 | 代码证据 | 验证结论 | 归档来源 | 关联待办 |
|---|---|---|---|---|---|
| ai-judge-p37-local-reference-regression-pack | P37 本地参考证据已刷新 | artifacts/harness/*p37*.json | local_reference_ready | AI_judge_service P37 阶段收口 | `ai-judge-p37-real-env-pass-window-execute-on-env` |
EOF_COMPLETED
  cat >"$root/docs/dev_plan/todo.md" <<'EOF_TODO'
# todo

### C41. AI Judge 平台化重构阶段收口（来源：当前开发计划）
| 债务项 | 来源模块 | 债务类型 | 当前不做原因 | 触发时机 | 完成定义（DoD） | 验证方式 |
|---|---|---|---|---|---|---|
| ai-judge-p37-real-env-pass-window-execute-on-env | `ai-judge-p37-local-reference-regression-pack` | 环境依赖 | P37 当前只有本地参考证据 | `REAL_CALIBRATION_ENV_READY=true` 后 | 输出真实环境 `pass` 工件 | 执行 runtime ops pack |
EOF_TODO
}

# 场景1：draft 有候选 + runtime pack 已就绪 -> pass
WORK_PASS="$TMP_DIR/pass"
PLAN_PASS="$WORK_PASS/plan-pass.md"
EVIDENCE_PASS="$WORK_PASS/docs/loadtest/evidence"
mkdir -p "$WORK_PASS" "$EVIDENCE_PASS"
write_plan_doc_with_candidates "$PLAN_PASS"
cat >"$EVIDENCE_PASS/ai_judge_runtime_ops_pack.env" <<'EOF_ENV'
AI_JUDGE_RUNTIME_OPS_PACK_STATUS=local_reference_ready
RELEASE_READINESS_ARTIFACT_STATUS=present
RELEASE_READINESS_ARTIFACT_SUMMARY_PATH=/tmp/test-ai-judge-release-readiness-artifact-summary.json
RELEASE_READINESS_ARTIFACT_REF=release-readiness-artifact-test
RELEASE_READINESS_ARTIFACT_MANIFEST_HASH=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
RELEASE_READINESS_ARTIFACT_DECISION=env_blocked
RELEASE_READINESS_ARTIFACT_STORAGE_MODE=local_reference
P41_CONTROL_PLANE_STATUS=env_blocked
P41_RUNTIME_READINESS_STATUS=ready
P41_CHAT_PROXY_STATUS=ready
P41_FRONTEND_CONTRACT_STATUS=ready
P41_CALIBRATION_DECISION_LOG_STATUS=ready
P41_PANEL_SHADOW_CANDIDATE_STATUS=env_blocked
P41_RUNTIME_OPS_PACK_STATUS=local_reference_ready
EOF_ENV
cat >"$EVIDENCE_PASS/ai_judge_runtime_ops_pack.md" <<'EOF_MD'
# runtime pack
EOF_MD

PASS_STDOUT="$TMP_DIR/pass.stdout"
PASS_JSON="$TMP_DIR/pass.summary.json"
PASS_MD="$TMP_DIR/pass.summary.md"

bash "$SCRIPT" \
  --root "$WORK_PASS" \
  --plan-doc "$PLAN_PASS" \
  --draft-script "$DRAFT_SCRIPT" \
  --emit-json "$PASS_JSON" \
  --emit-md "$PASS_MD" >"$PASS_STDOUT"

expect_contains "pass stdout status" "ai_judge_stage_closure_evidence_status: pass" "$PASS_STDOUT"
expect_contains "pass stdout linked" "runtime_ops_pack_linked: true" "$PASS_STDOUT"
expect_contains "pass stdout active plan" "active_plan_evidence_status: pass" "$PASS_STDOUT"
expect_contains "pass json status" "\"status\": \"pass\"" "$PASS_JSON"
expect_contains "pass json linked" "\"linked\": true" "$PASS_JSON"
expect_contains "pass json backfill" "\"closure_backfill\"" "$PASS_JSON"
expect_contains "pass release artifact" "\"artifact_ref\": \"release-readiness-artifact-test\"" "$PASS_JSON"
expect_contains "pass p41 status" "\"status\": \"env_blocked\"" "$PASS_JSON"
expect_contains "pass p41 stdout" "p41_panel_shadow_candidate_status: env_blocked" "$PASS_STDOUT"
expect_contains "pass markdown title" "# ai-judge-stage-closure-evidence" "$PASS_MD"

# 场景1b：runtime pack 已关联但 release artifact 缺失 -> evidence_missing
WORK_RELEASE_MISSING="$TMP_DIR/release-missing"
PLAN_RELEASE_MISSING="$WORK_RELEASE_MISSING/plan-release-missing.md"
EVIDENCE_RELEASE_MISSING="$WORK_RELEASE_MISSING/docs/loadtest/evidence"
mkdir -p "$WORK_RELEASE_MISSING" "$EVIDENCE_RELEASE_MISSING"
write_plan_doc_with_candidates "$PLAN_RELEASE_MISSING"
cat >"$EVIDENCE_RELEASE_MISSING/ai_judge_runtime_ops_pack.env" <<'EOF_ENV'
AI_JUDGE_RUNTIME_OPS_PACK_STATUS=local_reference_ready
RELEASE_READINESS_ARTIFACT_STATUS=missing
EOF_ENV
cat >"$EVIDENCE_RELEASE_MISSING/ai_judge_runtime_ops_pack.md" <<'EOF_MD'
# runtime pack
EOF_MD

RELEASE_MISSING_STDOUT="$TMP_DIR/release-missing.stdout"
RELEASE_MISSING_JSON="$TMP_DIR/release-missing.summary.json"
RELEASE_MISSING_MD="$TMP_DIR/release-missing.summary.md"

bash "$SCRIPT" \
  --root "$WORK_RELEASE_MISSING" \
  --plan-doc "$PLAN_RELEASE_MISSING" \
  --draft-script "$DRAFT_SCRIPT" \
  --emit-json "$RELEASE_MISSING_JSON" \
  --emit-md "$RELEASE_MISSING_MD" >"$RELEASE_MISSING_STDOUT"

expect_contains "release missing status" "ai_judge_stage_closure_evidence_status: evidence_missing" "$RELEASE_MISSING_STDOUT"
expect_contains "release missing artifact status" "release_readiness_artifact_status: missing" "$RELEASE_MISSING_STDOUT"
expect_contains "release missing json status" "\"status\": \"evidence_missing\"" "$RELEASE_MISSING_JSON"

# 场景2：draft 有候选 + runtime pack 缺失 -> pending_data
WORK_PENDING="$TMP_DIR/pending"
PLAN_PENDING="$WORK_PENDING/plan-pending.md"
mkdir -p "$WORK_PENDING"
write_plan_doc_with_candidates "$PLAN_PENDING"

PENDING_STDOUT="$TMP_DIR/pending.stdout"
PENDING_JSON="$TMP_DIR/pending.summary.json"
PENDING_MD="$TMP_DIR/pending.summary.md"

bash "$SCRIPT" \
  --root "$WORK_PENDING" \
  --plan-doc "$PLAN_PENDING" \
  --draft-script "$DRAFT_SCRIPT" \
  --emit-json "$PENDING_JSON" \
  --emit-md "$PENDING_MD" >"$PENDING_STDOUT"

expect_contains "pending stdout status" "ai_judge_stage_closure_evidence_status: pending_data" "$PENDING_STDOUT"
expect_contains "pending stdout linked" "runtime_ops_pack_linked: false" "$PENDING_STDOUT"
expect_contains "pending stdout active plan" "active_plan_evidence_status: pass" "$PENDING_STDOUT"
expect_contains "pending json status" "\"status\": \"pending_data\"" "$PENDING_JSON"

# 场景3：draft 无候选 + 无 archive -> stage_closure_archive_missing
WORK_MISSING="$TMP_DIR/missing"
PLAN_MISSING="$WORK_MISSING/plan-missing.md"
mkdir -p "$WORK_MISSING"
write_plan_doc_without_candidates "$PLAN_MISSING"

MISSING_STDOUT="$TMP_DIR/missing.stdout"
MISSING_JSON="$TMP_DIR/missing.summary.json"
MISSING_MD="$TMP_DIR/missing.summary.md"

bash "$SCRIPT" \
  --root "$WORK_MISSING" \
  --plan-doc "$PLAN_MISSING" \
  --draft-script "$DRAFT_SCRIPT" \
  --emit-json "$MISSING_JSON" \
  --emit-md "$MISSING_MD" >"$MISSING_STDOUT"

expect_contains "missing stdout status" "ai_judge_stage_closure_evidence_status: stage_closure_archive_missing" "$MISSING_STDOUT"
expect_contains "missing stdout archive missing" "closure_backfill_archive_status: stage_closure_archive_missing" "$MISSING_STDOUT"
expect_contains "missing json status" "\"status\": \"stage_closure_archive_missing\"" "$MISSING_JSON"
expect_contains "missing draft count" "\"completed_candidates_total\": 0" "$MISSING_JSON"
expect_contains "missing markdown runtime section" "## runtime_ops_pack" "$MISSING_MD"

# 场景4：活动计划已重置 + archive/completed/todo 可回填 -> pass
WORK_ARCHIVE="$TMP_DIR/archive-backfill"
PLAN_ARCHIVE="$WORK_ARCHIVE/plan-reset.md"
EVIDENCE_ARCHIVE="$WORK_ARCHIVE/docs/loadtest/evidence"
ARCHIVE_DIR="$WORK_ARCHIVE/docs/dev_plan/archive"
ARCHIVE_PATH="$ARCHIVE_DIR/20260425T111521Z-ai-judge-stage-closure-execute.md"
mkdir -p "$EVIDENCE_ARCHIVE" "$ARCHIVE_DIR"
write_long_term_docs "$WORK_ARCHIVE"
cat >"$ARCHIVE_PATH" <<'EOF_ARCHIVE'
# archived plan

### 已完成/未完成矩阵
| 阶段 | 目标 | 状态 | 说明 |
| --- | --- | --- | --- |
| ai-judge-p37-local-reference-regression-pack | P37 本地参考 | 已完成 | done |
EOF_ARCHIVE
write_reset_plan_with_archive "$PLAN_ARCHIVE" "$ARCHIVE_PATH"
cat >"$EVIDENCE_ARCHIVE/ai_judge_runtime_ops_pack.env" <<'EOF_ENV'
AI_JUDGE_RUNTIME_OPS_PACK_STATUS=local_reference_ready
RELEASE_READINESS_ARTIFACT_STATUS=present
RELEASE_READINESS_ARTIFACT_SUMMARY_PATH=/tmp/test-ai-judge-release-readiness-artifact-summary.json
RELEASE_READINESS_ARTIFACT_REF=release-readiness-artifact-test
RELEASE_READINESS_ARTIFACT_MANIFEST_HASH=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
RELEASE_READINESS_ARTIFACT_DECISION=env_blocked
RELEASE_READINESS_ARTIFACT_STORAGE_MODE=local_reference
P41_CONTROL_PLANE_STATUS=env_blocked
P41_RUNTIME_READINESS_STATUS=ready
P41_CHAT_PROXY_STATUS=ready
P41_FRONTEND_CONTRACT_STATUS=ready
P41_CALIBRATION_DECISION_LOG_STATUS=ready
P41_PANEL_SHADOW_CANDIDATE_STATUS=env_blocked
P41_RUNTIME_OPS_PACK_STATUS=local_reference_ready
EOF_ENV
cat >"$EVIDENCE_ARCHIVE/ai_judge_runtime_ops_pack.md" <<'EOF_MD'
# runtime pack
EOF_MD

ARCHIVE_STDOUT="$TMP_DIR/archive.stdout"
ARCHIVE_JSON="$TMP_DIR/archive.summary.json"
ARCHIVE_MD="$TMP_DIR/archive.summary.md"

bash "$SCRIPT" \
  --root "$WORK_ARCHIVE" \
  --plan-doc "$PLAN_ARCHIVE" \
  --draft-script "$DRAFT_SCRIPT" \
  --emit-json "$ARCHIVE_JSON" \
  --emit-md "$ARCHIVE_MD" >"$ARCHIVE_STDOUT"

expect_contains "archive stdout status" "ai_judge_stage_closure_evidence_status: pass" "$ARCHIVE_STDOUT"
expect_contains "archive detected" "closure_backfill_archive_detected: true" "$ARCHIVE_STDOUT"
expect_contains "archive source" "closure_backfill_archive_source: plan_doc" "$ARCHIVE_STDOUT"
expect_contains "archive completed section" "closure_backfill_completed_section: B41" "$ARCHIVE_STDOUT"
expect_contains "archive todo section" "closure_backfill_todo_section: C41" "$ARCHIVE_STDOUT"
expect_contains "archive real env debt" "closure_backfill_linked_real_env_debt_id: ai-judge-p37-real-env-pass-window-execute-on-env" "$ARCHIVE_STDOUT"
expect_contains "archive json completed count" "\"completed_module_count\": 1" "$ARCHIVE_JSON"
expect_contains "archive md closure section" "## closure_backfill" "$ARCHIVE_MD"

echo "all ai-judge stage closure evidence tests passed"
