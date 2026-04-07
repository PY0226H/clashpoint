#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)"
POST_MODULE_SCRIPT="$ROOT/skills/post-module-plan-sync/scripts/post_module_plan_sync.sh"
POST_OPT_SCRIPT="$ROOT/skills/post-optimization-plan-sync/scripts/post_optimization_plan_sync.sh"
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

expect_failure() {
  local name="$1"
  local pattern="$2"
  local file="$3"
  if grep -Fq -- "$pattern" "$file"; then
    echo "[PASS] $name"
    return
  fi
  echo "[FAIL] $name: missing failure pattern '$pattern'"
  echo "--- output ---"
  cat "$file"
  exit 1
}

WORKSPACE="$TMP_DIR/workspace"
mkdir -p "$WORKSPACE/.codex/plan-slots" "$WORKSPACE/docs/dev_plan/active"

cat >"$WORKSPACE/docs/dev_plan/当前开发计划.md" <<'EOF_DEFAULT'
# 当前开发计划

### 已完成/未完成矩阵

| 模块 | 优先级 | 状态 | 说明 |
|---|---|---|---|

### 下一开发模块建议

1. （待补充）

### 模块完成同步历史

- （待补充）
EOF_DEFAULT

cat >"$WORKSPACE/.codex/plan-slots/default.txt" <<'EOF_SLOT'
docs/dev_plan/当前开发计划.md
EOF_SLOT

DEFAULT_OUT="$TMP_DIR/default.out"
bash "$POST_MODULE_SCRIPT" \
  --root "$WORKSPACE" \
  --module auth-signin \
  --summary "sync default plan" \
  --dry-run >"$DEFAULT_OUT"

expect_contains "default slot resolves 当前开发计划" "目标计划文档 = $WORKSPACE/docs/dev_plan/当前开发计划.md" "$DEFAULT_OUT"

cat >"$WORKSPACE/docs/dev_plan/active/backend-signin.md" <<'EOF_BACKEND'
# backend signin

### 已完成/未完成矩阵

| 模块 | 优先级 | 状态 | 说明 |
|---|---|---|---|

### 下一开发模块建议

1. （待补充）

### 模块完成同步历史

- （待补充）
EOF_BACKEND

cat >"$WORKSPACE/docs/dev_plan/active/frontend-ui.md" <<'EOF_FRONTEND'
# frontend ui

### 已完成/未完成矩阵

| 模块 | 优先级 | 状态 | 说明 |
|---|---|---|---|

### 下一开发模块建议

1. （待补充）

### 模块完成同步历史

- （待补充）
EOF_FRONTEND

cat >"$WORKSPACE/.codex/plan-slots/backend-signin.txt" <<'EOF_BACKEND_SLOT'
docs/dev_plan/active/backend-signin.md
EOF_BACKEND_SLOT

cat >"$WORKSPACE/.codex/plan-slots/frontend-ui.txt" <<'EOF_FRONTEND_SLOT'
docs/dev_plan/active/frontend-ui.md
EOF_FRONTEND_SLOT

MULTI_ERR="$TMP_DIR/multi.err"
if bash "$POST_MODULE_SCRIPT" \
  --root "$WORKSPACE" \
  --module auth-signin \
  --summary "should fail on ambiguous slots" \
  --dry-run > /dev/null 2>"$MULTI_ERR"; then
  echo "[FAIL] multiple active slots should require explicit slot"
  exit 1
fi

expect_failure "multiple slots refuse guessing" "检测到多个活动计划 slot" "$MULTI_ERR"

BACKEND_OUT="$TMP_DIR/backend.out"
bash "$POST_MODULE_SCRIPT" \
  --root "$WORKSPACE" \
  --slot backend-signin \
  --module auth-signin \
  --summary "sync backend slot" \
  --dry-run >"$BACKEND_OUT"

expect_contains "explicit slot resolves backend plan" "slot = backend-signin" "$BACKEND_OUT"
expect_contains "explicit slot points backend doc" "目标计划文档 = $WORKSPACE/docs/dev_plan/active/backend-signin.md" "$BACKEND_OUT"

cat >"$WORKSPACE/docs/dev_plan/active/backend-refactor.md" <<'EOF_OPT'
# backend refactor

## 8. 优化执行矩阵

| 阶段 | 标题 | 状态 | 说明 |
|---|---|---|---|

## 9. 下一步优化建议

1. （待补充）

## 10. 优化回写记录

- （待补充）
EOF_OPT

cat >"$WORKSPACE/.codex/plan-slots/backend-refactor.txt" <<'EOF_OPT_SLOT'
docs/dev_plan/active/backend-refactor.md
EOF_OPT_SLOT

OPT_OUT="$TMP_DIR/opt.out"
bash "$POST_OPT_SCRIPT" \
  --root "$WORKSPACE" \
  --slot backend-refactor \
  --stage R1 \
  --module auth-refactor \
  --summary "refactor auth flow" \
  --status done >"$OPT_OUT"

expect_contains "optimization slot updates target file" "auth-refactor" "$WORKSPACE/docs/dev_plan/active/backend-refactor.md"

echo "all plan slot resolution tests passed"
