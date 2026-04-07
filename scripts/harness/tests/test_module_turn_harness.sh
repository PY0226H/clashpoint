#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
SCRIPT="$ROOT/scripts/harness/module_turn_harness.sh"

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

DEV_OUT="$TMP_DIR/dev.out"
bash "$SCRIPT" \
  --root "$ROOT" \
  --task-kind dev \
  --slot backend-signin \
  --module lobby-copy-tune \
  --summary "polish lobby copy wording" \
  --dry-run >"$DEV_OUT"

expect_contains "dev dry-run announces mode" "mode: dry-run" "$DEV_OUT"
expect_contains "dev dry-run announces slot" "slot: backend-signin" "$DEV_OUT"
expect_contains "dev dry-run announces prd mode" "prd-mode: auto" "$DEV_OUT"
expect_contains "dev dry-run announces knowledge pack mode" "knowledge-pack: auto" "$DEV_OUT"
expect_contains "dev dry-run includes prd gate" "[pre-prd] PRD 对齐" "$DEV_OUT"
expect_contains "dev dry-run defaults to summary prd gate" "prd_mode_effective: summary" "$DEV_OUT"
expect_contains "dev dry-run includes test guard" "[post-test-guard] 测试变更检查与测试门禁" "$DEV_OUT"
expect_contains "dev dry-run includes plan sync" "[post-plan-sync] 同步开发计划文档" "$DEV_OUT"
expect_contains "dev dry-run passes slot to plan sync" "--slot backend-signin" "$DEV_OUT"
expect_contains "dev dry-run records knowledge pack decision" "[knowledge-pack] knowledge pack 决策" "$DEV_OUT"
expect_contains "dev dry-run defaults to skipping knowledge pack" "effective_mode: skip" "$DEV_OUT"

HIGH_RISK_OUT="$TMP_DIR/high-risk.out"
bash "$SCRIPT" \
  --root "$ROOT" \
  --task-kind dev \
  --module auth-session-hardening \
  --summary "tighten signin token and sms verification flow" \
  --dry-run >"$HIGH_RISK_OUT"

expect_contains "high-risk dry-run escalates prd gate" "prd_mode_effective: full" "$HIGH_RISK_OUT"
expect_contains "high-risk dry-run explains escalation" "full_prd_reason: 命中高风险认证/权限关键词: auth" "$HIGH_RISK_OUT"
expect_contains "high-risk dry-run enables knowledge pack" "effective_mode: run" "$HIGH_RISK_OUT"
expect_contains "high-risk dry-run includes interview journal" "[post-interview-journal] 更新 interview 文档" "$HIGH_RISK_OUT"
expect_contains "high-risk dry-run includes explanation journal" "[post-explanation-journal] 生成 explanation 文档" "$HIGH_RISK_OUT"

FORCE_PACK_OUT="$TMP_DIR/force-pack.out"
bash "$SCRIPT" \
  --root "$ROOT" \
  --task-kind dev \
  --module tiny-doc-fix \
  --summary "small module follow-up" \
  --knowledge-pack force \
  --dry-run >"$FORCE_PACK_OUT"

expect_contains "force knowledge pack is announced" "knowledge-pack: force" "$FORCE_PACK_OUT"
expect_contains "force knowledge pack reason is printed" "reason: 显式指定 --knowledge-pack force" "$FORCE_PACK_OUT"
expect_contains "force knowledge pack includes interview journal" "[post-interview-journal] 更新 interview 文档" "$FORCE_PACK_OUT"

REFACTOR_OUT="$TMP_DIR/refactor.out"
bash "$SCRIPT" \
  --root "$ROOT" \
  --task-kind refactor \
  --module harness-refactor \
  --summary "refactor module harness flow" \
  --dry-run >"$REFACTOR_OUT"

expect_contains "refactor dry-run uses optimization sync" "[post-optimization-plan-sync] 同步优化计划文档" "$REFACTOR_OUT"

NON_DEV_OUT="$TMP_DIR/nondev.out"
bash "$SCRIPT" \
  --root "$ROOT" \
  --task-kind non-dev \
  --module harness-docs \
  --summary "sync harness docs" \
  --dry-run >"$NON_DEV_OUT"

expect_contains "non-dev enters light mode" "[non-dev] 轻量模式" "$NON_DEV_OUT"
expect_contains "non-dev dry-run includes docs lint" "[docs-lint] 文档结构检查" "$NON_DEV_OUT"
expect_contains "non-dev prints commit suggestion" "Recommended:" "$NON_DEV_OUT"

NON_DEV_EXEC_OUT="$TMP_DIR/nondev-exec.out"
bash "$SCRIPT" \
  --root "$ROOT" \
  --task-kind non-dev \
  --module harness-structured-logs \
  --summary "verify structured harness artifacts" >"$NON_DEV_EXEC_OUT"

SUMMARY_JSON="$(awk -F ': ' '/^artifact_summary_json:/ { print $2; exit }' "$NON_DEV_EXEC_OUT")"
SUMMARY_MD="$(awk -F ': ' '/^artifact_summary_md:/ { print $2; exit }' "$NON_DEV_EXEC_OUT")"
JSONL_FILE="$(awk -F ': ' '/^artifact_jsonl:/ { print $2; exit }' "$NON_DEV_EXEC_OUT")"

if [[ ! -f "$SUMMARY_JSON" || ! -f "$SUMMARY_MD" || ! -f "$JSONL_FILE" ]]; then
  echo "[FAIL] execute mode should generate harness artifacts"
  cat "$NON_DEV_EXEC_OUT"
  exit 1
fi

expect_contains "summary json records module" "\"module\": \"harness-structured-logs\"" "$SUMMARY_JSON"
expect_contains "summary json records docs-lint step" "\"step_id\":\"docs-lint\"" "$SUMMARY_JSON"
expect_contains "summary md includes steps table" "## Steps" "$SUMMARY_MD"
expect_contains "jsonl contains run_finished event" "\"event\":\"run_finished\"" "$JSONL_FILE"

echo "all module-turn-harness tests passed"
