#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
SCRIPT="$ROOT/scripts/quality/harness_docs_lint.sh"
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

make_workspace() {
  local workspace="$1"
  mkdir -p "$workspace/.codex/plan-slots" "$workspace/docs/dev_plan/active" "$workspace/docs/harness"

  cat >"$workspace/.codex/plan-slots/default.txt" <<'EOF_DEFAULT_SLOT'
docs/dev_plan/当前开发计划.md
EOF_DEFAULT_SLOT

  cat >"$workspace/docs/dev_plan/当前开发计划.md" <<'EOF_CURRENT_PLAN'
# 当前开发计划

## 1. 文档角色

1. 本文档是默认活动计划。

## 2. 当前计划概览

- 关联 slot：`default`

### 已完成/未完成矩阵

| 模块 | 优先级 | 状态 | 说明 |
|---|---|---|---|
| docs-lint | P1 | 进行中 | 正在实现 docs lint。 |

### 下一开发模块建议

1. 补齐 CI 挂接。

### 模块完成同步历史

- 2026-04-06：初始化当前开发计划。
EOF_CURRENT_PLAN

  cat >"$workspace/docs/dev_plan/todo.md" <<'EOF_TODO'
# todo.md

## A. 文档说明

1. 本文件只记录技术债。

## B. 当前写入区

| 债务项 | 来源模块 | 债务类型 | 当前不做原因 | 触发时机 | 完成定义（DoD） | 验证方式 |
|---|---|---|---|---|---|---|
| docs-lint-ci | docs-lint | 工程债 | 当前先完成本地规则落地 | CI 接入时 | 能在 CI 中执行 | build.yml 增加调用 |
EOF_TODO

  cat >"$workspace/docs/dev_plan/completed.md" <<'EOF_COMPLETED'
# completed.md

## A. 已完成

| 模块 | 结论 | 代码证据 | 验证结论 | 归档来源 | 关联待办 |
|---|---|---|---|---|---|
| p1-3 | 已完成 | scripts/quality/harness_docs_lint.sh | 本地校验通过 | 主开发计划阶段收口 | （无） |
EOF_COMPLETED

  cat >"$workspace/docs/harness/00-overview.md" <<'EOF_HARNESS'
# Harness Overview

更新时间：2026-04-06
状态：已生效

## 1. 目的

1. 提供规则导航。
EOF_HARNESS
}

WORKSPACE_OK="$TMP_DIR/workspace-ok"
make_workspace "$WORKSPACE_OK"

OK_STDOUT="$TMP_DIR/ok.stdout"
OK_JSON="$TMP_DIR/ok.json"
OK_MD="$TMP_DIR/ok.md"
bash "$SCRIPT" \
  --root "$WORKSPACE_OK" \
  --json-out "$OK_JSON" \
  --md-out "$OK_MD" >"$OK_STDOUT"

expect_contains "happy path prints pass" "status: PASS" "$OK_STDOUT"
expect_contains "happy path json ok" '"ok": true' "$OK_JSON"
expect_contains "happy path markdown checked section" "## Checked" "$OK_MD"

WORKSPACE_BLANK_PLAN="$TMP_DIR/workspace-blank-current-plan"
make_workspace "$WORKSPACE_BLANK_PLAN"
: >"$WORKSPACE_BLANK_PLAN/docs/dev_plan/当前开发计划.md"

BLANK_PLAN_STDOUT="$TMP_DIR/blank-plan.stdout"
BLANK_PLAN_JSON="$TMP_DIR/blank-plan.json"
BLANK_PLAN_MD="$TMP_DIR/blank-plan.md"
bash "$SCRIPT" \
  --root "$WORKSPACE_BLANK_PLAN" \
  --json-out "$BLANK_PLAN_JSON" \
  --md-out "$BLANK_PLAN_MD" >"$BLANK_PLAN_STDOUT"

expect_contains "blank current plan is allowed" "status: PASS" "$BLANK_PLAN_STDOUT"
expect_contains "blank current plan json ok" '"ok": true' "$BLANK_PLAN_JSON"

WORKSPACE_EMPTY="$TMP_DIR/workspace-empty-pointer"
make_workspace "$WORKSPACE_EMPTY"
: >"$WORKSPACE_EMPTY/.codex/plan-slots/default.txt"

EMPTY_STDOUT="$TMP_DIR/empty.stdout"
EMPTY_JSON="$TMP_DIR/empty.json"
EMPTY_MD="$TMP_DIR/empty.md"
if bash "$SCRIPT" \
  --root "$WORKSPACE_EMPTY" \
  --json-out "$EMPTY_JSON" \
  --md-out "$EMPTY_MD" >"$EMPTY_STDOUT"; then
  echo "[FAIL] empty pointer should fail"
  exit 1
fi

expect_contains "empty pointer reports error code" '"code":"default_slot_pointer_empty"' "$EMPTY_JSON"
expect_contains "empty pointer markdown fail" "status: FAIL" "$EMPTY_MD"

WORKSPACE_DANGLING="$TMP_DIR/workspace-dangling-slot"
make_workspace "$WORKSPACE_DANGLING"
cat >"$WORKSPACE_DANGLING/.codex/plan-slots/backend-signin.txt" <<'EOF_DANGLING_SLOT'
docs/dev_plan/active/backend-signin.md
EOF_DANGLING_SLOT

DANGLING_JSON="$TMP_DIR/dangling.json"
DANGLING_MD="$TMP_DIR/dangling.md"
if bash "$SCRIPT" \
  --root "$WORKSPACE_DANGLING" \
  --json-out "$DANGLING_JSON" \
  --md-out "$DANGLING_MD" > /dev/null; then
  echo "[FAIL] dangling slot target should fail"
  exit 1
fi

expect_contains "dangling slot target reports error" '"code":"slot_target_missing"' "$DANGLING_JSON"

echo "all harness docs lint tests passed"
