#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
SCRIPT="$ROOT/scripts/harness/ai_judge_stage_closure_execute.sh"

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

expect_not_contains() {
  local name="$1"
  local pattern="$2"
  local file="$3"
  if grep -Fq -- "$pattern" "$file"; then
    echo "[FAIL] $name: unexpected pattern '$pattern'"
    echo "--- output ---"
    cat "$file"
    exit 1
  fi
  echo "[PASS] $name"
}

WORK_ROOT="$TMP_DIR/work-root"
mkdir -p "$WORK_ROOT/docs/dev_plan" "$WORK_ROOT/artifacts/harness"

PLAN_DOC="$WORK_ROOT/docs/dev_plan/当前开发计划.md"
COMPLETED_DOC="$WORK_ROOT/docs/dev_plan/completed.md"
TODO_DOC="$WORK_ROOT/docs/dev_plan/todo.md"
ARCHIVE_DIR="$WORK_ROOT/docs/dev_plan/archive"

cat >"$PLAN_DOC" <<'PLAN_EOF'
# 当前开发计划

### 已完成/未完成矩阵
| 阶段 | 目标 | 状态 | 说明 |
| --- | --- | --- | --- |
| ai-judge-module-a | P1 | 进行中（phase 已完成） | done-a |
| ai-judge-module-b | P1 | 进行中 | doing-b |
| ai-judge-p5-calibration-prep | P5 | 进行中（prep 已完成） | done-p5 |

## 5. 延后事项（不阻塞当前阶段）

1. 真实线上压测数据驱动的容量规划
2. 真实请求延迟分布驱动的 SLA 阈值冻结

### 下一开发模块建议

1. ai-judge-stage-closure-execute
2. ai-judge-p5-real-calibration-on-env
PLAN_EOF

cat >"$COMPLETED_DOC" <<'COMPLETED_EOF'
# completed.md

## A. 文档说明

## B. 当前写入区（新结构）
COMPLETED_EOF

cat >"$TODO_DOC" <<'TODO_EOF'
# todo.md

## A. 文档说明

## C. 当前写入区（新结构）
TODO_EOF

STDOUT_FILE="$TMP_DIR/execute.stdout"
OUT_JSON="$TMP_DIR/execute.summary.json"
OUT_MD="$TMP_DIR/execute.summary.md"

bash "$SCRIPT" \
  --root "$WORK_ROOT" \
  --plan-doc "$PLAN_DOC" \
  --completed-doc "$COMPLETED_DOC" \
  --todo-doc "$TODO_DOC" \
  --archive-dir "$ARCHIVE_DIR" \
  --emit-json "$OUT_JSON" \
  --emit-md "$OUT_MD" >"$STDOUT_FILE"

expect_contains "stdout status" "ai_judge_stage_closure_execute_status: pass" "$STDOUT_FILE"
expect_contains "stdout archive" "archive_path:" "$STDOUT_FILE"

expect_contains "completed new section" "### B1. AI Judge 平台化重构阶段收口（来源：当前开发计划）" "$COMPLETED_DOC"
expect_contains "completed includes module-a" "| ai-judge-module-a |" "$COMPLETED_DOC"
expect_contains "completed includes p5-prep" "| ai-judge-p5-calibration-prep |" "$COMPLETED_DOC"
expect_not_contains "completed excludes module-b" "| ai-judge-module-b |" "$COMPLETED_DOC"

expect_contains "todo new section" "### C1. AI Judge 平台化重构阶段收口（来源：当前开发计划）" "$TODO_DOC"
expect_contains "todo deferred01" "| ai-judge-stage-closure-deferred-01 |" "$TODO_DOC"
expect_contains "todo deferred02" "| ai-judge-stage-closure-deferred-02 |" "$TODO_DOC"
expect_contains "todo p5 debt" "| ai-judge-p5-real-calibration-on-env |" "$TODO_DOC"

expect_contains "plan reset mainline" "当前主线：\`AI_judge_service 下一阶段（待规划）\`" "$PLAN_DOC"
expect_contains "plan reset module" "| \`ai-judge-stage-closure-execute\` | AI judge 当前阶段收口执行 | 已完成 |" "$PLAN_DOC"
expect_contains "plan reset next iteration" "1. ai-judge-next-iteration-planning" "$PLAN_DOC"

expect_contains "json completed count" '"completed_appended": 2' "$OUT_JSON"
expect_contains "json todo count" '"todo_appended": 3' "$OUT_JSON"
expect_contains "markdown summary" "# AI Judge Stage Closure Execute" "$OUT_MD"

ARCHIVE_FILE_COUNT="$(find "$ARCHIVE_DIR" -maxdepth 1 -type f -name '*-ai-judge-stage-closure-execute.md' | wc -l | tr -d ' ')"
if [[ "$ARCHIVE_FILE_COUNT" != "1" ]]; then
  echo "[FAIL] archive file count: expected 1 got $ARCHIVE_FILE_COUNT"
  find "$ARCHIVE_DIR" -maxdepth 2 -type f -print
  exit 1
fi

echo "all ai-judge stage closure execute tests passed"
