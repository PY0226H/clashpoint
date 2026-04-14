#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
SCRIPT="$ROOT/scripts/harness/ai_judge_next_plan_bootstrap.sh"

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

expect_equals() {
  local name="$1"
  local expected="$2"
  local actual="$3"
  if [[ "$expected" == "$actual" ]]; then
    echo "[PASS] $name"
    return
  fi
  echo "[FAIL] $name: expected '$expected' got '$actual'"
  exit 1
}

WORK_ROOT="$TMP_DIR/work-root"
mkdir -p "$WORK_ROOT/docs/dev_plan" "$WORK_ROOT/artifacts/harness"

PLAN_DOC="$WORK_ROOT/docs/dev_plan/当前开发计划.md"
MAPPING_DOC="$WORK_ROOT/docs/dev_plan/mapping.md"

cat >"$MAPPING_DOC" <<'MAP_EOF'
# mapping
MAP_EOF

cat >"$PLAN_DOC" <<'PLAN_EOF'
# 当前开发计划

关联 slot：`default`  
更新时间：2026-04-13  
当前主线：`旧主线`  
当前状态：进行中（旧状态）

---

## 1. 计划定位

1. 示例。
PLAN_EOF

# 场景1：首次执行，追加 bootstrap 块
FIRST_STDOUT="$TMP_DIR/first.stdout"
FIRST_JSON="$TMP_DIR/first.summary.json"
FIRST_MD="$TMP_DIR/first.summary.md"

bash "$SCRIPT" \
  --root "$WORK_ROOT" \
  --plan-doc "$PLAN_DOC" \
  --mapping-doc "$MAPPING_DOC" \
  --emit-json "$FIRST_JSON" \
  --emit-md "$FIRST_MD" >"$FIRST_STDOUT"

expect_contains "first status" "ai_judge_next_plan_bootstrap_status: pass" "$FIRST_STDOUT"
expect_contains "first operation appended" "operation: appended" "$FIRST_STDOUT"
expect_contains "first marker count" "bootstrap_marker_count: 1" "$FIRST_STDOUT"
expect_contains "header mainline updated" "当前主线：\`AI_judge_service 下一阶段（P5 校准与公平门禁补强）\`" "$PLAN_DOC"
expect_contains "header status updated" "当前状态：进行中（next-plan bootstrapped）" "$PLAN_DOC"
expect_contains "block start marker" "<!-- AI_JUDGE_NEXT_PLAN_BOOTSTRAP:START -->" "$PLAN_DOC"
expect_contains "block end marker" "<!-- AI_JUDGE_NEXT_PLAN_BOOTSTRAP:END -->" "$PLAN_DOC"
expect_contains "json appended" '"operation": "appended"' "$FIRST_JSON"
expect_contains "markdown title" "# AI Judge Next Plan Bootstrap" "$FIRST_MD"

BLOCK_COUNT_FIRST="$(grep -F "AI_JUDGE_NEXT_PLAN_BOOTSTRAP:START" "$PLAN_DOC" | wc -l | tr -d ' ')"
expect_equals "first marker occurrences" "1" "$BLOCK_COUNT_FIRST"

# 场景2：重复执行，替换同一块（幂等）
SECOND_STDOUT="$TMP_DIR/second.stdout"
SECOND_JSON="$TMP_DIR/second.summary.json"
SECOND_MD="$TMP_DIR/second.summary.md"

bash "$SCRIPT" \
  --root "$WORK_ROOT" \
  --plan-doc "$PLAN_DOC" \
  --mapping-doc "$MAPPING_DOC" \
  --emit-json "$SECOND_JSON" \
  --emit-md "$SECOND_MD" >"$SECOND_STDOUT"

expect_contains "second status" "ai_judge_next_plan_bootstrap_status: pass" "$SECOND_STDOUT"
expect_contains "second operation replaced" "operation: replaced" "$SECOND_STDOUT"
expect_contains "second marker count" "bootstrap_marker_count: 1" "$SECOND_STDOUT"
expect_contains "second json replaced" '"operation": "replaced"' "$SECOND_JSON"

BLOCK_COUNT_SECOND="$(grep -F "AI_JUDGE_NEXT_PLAN_BOOTSTRAP:START" "$PLAN_DOC" | wc -l | tr -d ' ')"
expect_equals "second marker occurrences" "1" "$BLOCK_COUNT_SECOND"

BLUEPRINT_COUNT="$(grep -F "## 2. 下一阶段执行蓝图（P5→P6）" "$PLAN_DOC" | wc -l | tr -d ' ')"
expect_equals "blueprint section occurrences" "1" "$BLUEPRINT_COUNT"

# 场景3：存在多个 marker，脚本应 fail
BROKEN_PLAN="$TMP_DIR/broken-plan.md"
cat >"$BROKEN_PLAN" <<'BROKEN_EOF'
# 当前开发计划

更新时间：2026-04-13
当前主线：`x`
当前状态：进行中

<!-- AI_JUDGE_NEXT_PLAN_BOOTSTRAP:START -->
A
<!-- AI_JUDGE_NEXT_PLAN_BOOTSTRAP:END -->

<!-- AI_JUDGE_NEXT_PLAN_BOOTSTRAP:START -->
B
<!-- AI_JUDGE_NEXT_PLAN_BOOTSTRAP:END -->
BROKEN_EOF

BROKEN_STDOUT="$TMP_DIR/broken.stdout"
set +e
bash "$SCRIPT" \
  --root "$WORK_ROOT" \
  --plan-doc "$BROKEN_PLAN" \
  --mapping-doc "$MAPPING_DOC" >"$BROKEN_STDOUT" 2>&1
BROKEN_EXIT="$?"
set -e

if [[ "$BROKEN_EXIT" -eq 0 ]]; then
  echo "[FAIL] broken marker scenario: expected non-zero exit"
  cat "$BROKEN_STDOUT"
  exit 1
fi
expect_contains "broken status fail" "ai_judge_next_plan_bootstrap_status: fail" "$BROKEN_STDOUT"
expect_contains "broken marker count" "bootstrap_marker_count: 2" "$BROKEN_STDOUT"

echo "all ai-judge next plan bootstrap tests passed"
