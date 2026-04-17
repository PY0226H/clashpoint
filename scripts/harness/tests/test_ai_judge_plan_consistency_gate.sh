#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
SCRIPT="$ROOT/scripts/harness/ai_judge_plan_consistency_gate.sh"

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

write_arch_doc() {
  local file="$1"
  cat >"$file" <<'EOF_ARCH'
# 架构文档摘录

## 13. 与企业方案的一致性检查清单（必须通过）

1. **角色一致性**：8 Agent 职责是否完整映射，是否被错误合并或绕过。
2. **数据一致性**：`case_dossier/claim_graph/evidence_bundle/verdict_ledger/fairness_report/opinion_pack` 是否有对应存储与追踪路径。
3. **门禁一致性**：`Fairness Sentinel` 是否仍在终判前，override 是否可审计。
4. **边界一致性**：`NPC/Room QA` 是否严格保持 advisory-only，不写官方裁决链。
5. **跨层一致性**：契约变更是否在 `chat_server` 与调用方同轮更新。
6. **收口一致性**：real-env 项是否区分 `local_reference_ready` 与 `pass`，不混淆口径。
EOF_ARCH
}

write_plan_pass() {
  local file="$1"
  cat >"$file" <<'EOF_PLAN'
# 当前开发计划

## 12. 架构方案第13章一致性校验（计划生成前置）

1. **角色一致性**：8 Agent 主链已在 runtime 显式建模，职责未被错误合并。
2. **数据一致性**：`case_dossier/claim_graph/evidence_bundle/verdict_ledger/fairness_report/opinion_pack` 均有读写与回放路径。
3. **门禁一致性**：`Fairness Sentinel` 位于 `Chief Arbiter` 之前，override 会写审计链路。
4. **边界一致性**：`NPC/Room QA` 维持 `advisory_only`，不写入官方裁决链。
5. **跨层一致性**：final 契约字段变更已在 `chat_server` 同轮同步，不保留旧字段 alias。
6. **收口一致性**：real-env 仍区分 `local_reference_ready` 与真实 `pass`，当前未混淆口径。
EOF_PLAN
}

WORK_ROOT="$TMP_DIR/work-root"
mkdir -p "$WORK_ROOT/docs/dev_plan" "$WORK_ROOT/artifacts/harness"

ARCH_DOC="$WORK_ROOT/docs/dev_plan/arch.md"
PLAN_DOC="$WORK_ROOT/docs/dev_plan/plan.md"

write_arch_doc "$ARCH_DOC"
write_plan_pass "$PLAN_DOC"

# 场景1：完整回答 -> pass
PASS_STDOUT="$TMP_DIR/pass.stdout"
PASS_JSON="$TMP_DIR/pass.summary.json"
PASS_MD="$TMP_DIR/pass.summary.md"

bash "$SCRIPT" \
  --root "$WORK_ROOT" \
  --plan-doc "$PLAN_DOC" \
  --arch-doc "$ARCH_DOC" \
  --emit-json "$PASS_JSON" \
  --emit-md "$PASS_MD" >"$PASS_STDOUT"

expect_contains "pass status" "ai_judge_plan_consistency_gate_status: pass" "$PASS_STDOUT"
expect_contains "pass section found" "consistency_section_found: true" "$PASS_STDOUT"
expect_contains "pass json status" "\"status\": \"pass\"" "$PASS_JSON"
expect_contains "pass md title" "# ai-judge-plan-consistency-gate" "$PASS_MD"

# 场景2：缺项 -> fail
MISSING_PLAN="$WORK_ROOT/docs/dev_plan/plan-missing.md"
cat >"$MISSING_PLAN" <<'EOF_MISSING'
# 当前开发计划

## 12. 架构方案第13章一致性校验（计划生成前置）

1. **角色一致性**：8 Agent 主链已在 runtime 显式建模。
2. **数据一致性**：六对象有读写路径。
3. **门禁一致性**：`Fairness Sentinel` 位于终判前。
4. **边界一致性**：`NPC/Room QA` 保持 advisory-only。
6. **收口一致性**：real-env 未混淆 `local_reference_ready` 和 `pass`。
EOF_MISSING

MISSING_STDOUT="$TMP_DIR/missing.stdout"
set +e
bash "$SCRIPT" \
  --root "$WORK_ROOT" \
  --plan-doc "$MISSING_PLAN" \
  --arch-doc "$ARCH_DOC" >"$MISSING_STDOUT" 2>&1
MISSING_EXIT="$?"
set -e

if [[ "$MISSING_EXIT" -eq 0 ]]; then
  echo "[FAIL] missing scenario: expected non-zero exit"
  cat "$MISSING_STDOUT"
  exit 1
fi
expect_contains "missing status" "ai_judge_plan_consistency_gate_status: fail" "$MISSING_STDOUT"
expect_contains "missing item output" "missing_items: 跨层一致性" "$MISSING_STDOUT"

# 场景3：占位答案 -> fail
PLACEHOLDER_PLAN="$WORK_ROOT/docs/dev_plan/plan-placeholder.md"
cat >"$PLACEHOLDER_PLAN" <<'EOF_PLACEHOLDER'
# 当前开发计划

## 12. 架构方案第13章一致性校验（计划生成前置）

1. **角色一致性**：待补充
2. **数据一致性**：六对象有读写路径。
3. **门禁一致性**：`Fairness Sentinel` 位于终判前。
4. **边界一致性**：`NPC/Room QA` 保持 advisory-only。
5. **跨层一致性**：final 契约已同轮同步。
6. **收口一致性**：real-env 未混淆 `local_reference_ready` 和 `pass`。
EOF_PLACEHOLDER

PLACEHOLDER_STDOUT="$TMP_DIR/placeholder.stdout"
set +e
bash "$SCRIPT" \
  --root "$WORK_ROOT" \
  --plan-doc "$PLACEHOLDER_PLAN" \
  --arch-doc "$ARCH_DOC" >"$PLACEHOLDER_STDOUT" 2>&1
PLACEHOLDER_EXIT="$?"
set -e

if [[ "$PLACEHOLDER_EXIT" -eq 0 ]]; then
  echo "[FAIL] placeholder scenario: expected non-zero exit"
  cat "$PLACEHOLDER_STDOUT"
  exit 1
fi
expect_contains "placeholder status" "ai_judge_plan_consistency_gate_status: fail" "$PLACEHOLDER_STDOUT"
expect_contains "placeholder item output" "placeholder_items: 角色一致性" "$PLACEHOLDER_STDOUT"

# 场景4：缺少一致性章节 -> fail
NO_SECTION_PLAN="$WORK_ROOT/docs/dev_plan/plan-no-section.md"
cat >"$NO_SECTION_PLAN" <<'EOF_NOSECTION'
# 当前开发计划

## 10. 其它章节

1. 本文档没有一致性校验章节。
EOF_NOSECTION

NO_SECTION_STDOUT="$TMP_DIR/no-section.stdout"
set +e
bash "$SCRIPT" \
  --root "$WORK_ROOT" \
  --plan-doc "$NO_SECTION_PLAN" \
  --arch-doc "$ARCH_DOC" >"$NO_SECTION_STDOUT" 2>&1
NO_SECTION_EXIT="$?"
set -e

if [[ "$NO_SECTION_EXIT" -eq 0 ]]; then
  echo "[FAIL] no-section scenario: expected non-zero exit"
  cat "$NO_SECTION_STDOUT"
  exit 1
fi
expect_contains "no-section status" "ai_judge_plan_consistency_gate_status: fail" "$NO_SECTION_STDOUT"
expect_contains "no-section flag" "consistency_section_found: false" "$NO_SECTION_STDOUT"

echo "all ai_judge_plan_consistency_gate tests passed"
