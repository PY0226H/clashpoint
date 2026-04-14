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

# 场景1：draft 有候选 + runtime pack 已就绪 -> pass
WORK_PASS="$TMP_DIR/pass"
PLAN_PASS="$WORK_PASS/plan-pass.md"
EVIDENCE_PASS="$WORK_PASS/docs/loadtest/evidence"
mkdir -p "$WORK_PASS" "$EVIDENCE_PASS"
write_plan_doc_with_candidates "$PLAN_PASS"
cat >"$EVIDENCE_PASS/ai_judge_runtime_ops_pack.env" <<'EOF_ENV'
AI_JUDGE_RUNTIME_OPS_PACK_STATUS=local_reference_ready
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
expect_contains "pass json status" "\"status\": \"pass\"" "$PASS_JSON"
expect_contains "pass json linked" "\"linked\": true" "$PASS_JSON"
expect_contains "pass markdown title" "# ai-judge-stage-closure-evidence" "$PASS_MD"

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
expect_contains "pending json status" "\"status\": \"pending_data\"" "$PENDING_JSON"

# 场景3：draft 无候选 -> evidence_missing
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

expect_contains "missing stdout status" "ai_judge_stage_closure_evidence_status: evidence_missing" "$MISSING_STDOUT"
expect_contains "missing json status" "\"status\": \"evidence_missing\"" "$MISSING_JSON"
expect_contains "missing draft count" "\"completed_candidates_total\": 0" "$MISSING_JSON"
expect_contains "missing markdown runtime section" "## runtime_ops_pack" "$MISSING_MD"

echo "all ai-judge stage closure evidence tests passed"
