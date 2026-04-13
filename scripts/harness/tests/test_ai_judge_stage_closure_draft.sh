#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
SCRIPT="$ROOT/scripts/harness/ai_judge_stage_closure_draft.sh"

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

PLAN="$TMP_DIR/plan.md"
cat >"$PLAN" <<'PLAN_EOF'
# 当前开发计划

### 已完成/未完成矩阵
| 阶段 | 目标 | 状态 | 说明 |
| --- | --- | --- | --- |
| `P0` | x | 已完成 | ok |
| ai-judge-module-a | P2 | 进行中（phase 已完成） | module-a done |
| ai-judge-module-b | P3 | 进行中 | module-b doing |
| ai-judge-p5-calibration-prep | P5 | 进行中（prep 已完成） | p5 prep done |

## 5. 延后事项（不阻塞当前阶段）

1. 真实压测样本不足
2. 真实成本账单尚未接入

### 下一开发模块建议

1. ai-judge-stage-closure-draft
2. ai-judge-p5-real-calibration-on-env
PLAN_EOF

OUT_STD="$TMP_DIR/stdout.txt"
OUT_JSON="$TMP_DIR/out.summary.json"
OUT_MD="$TMP_DIR/out.summary.md"

bash "$SCRIPT" \
  --root "$TMP_DIR" \
  --plan-doc "$PLAN" \
  --emit-json "$OUT_JSON" \
  --emit-md "$OUT_MD" >"$OUT_STD"

expect_contains "stdout status" "ai_judge_stage_closure_draft_status: pass" "$OUT_STD"
expect_contains "stdout completed count" "completed_candidates_total: 2" "$OUT_STD"
expect_contains "stdout todo count" "todo_candidates_total: 3" "$OUT_STD"

expect_contains "json includes module-a" '"module":"ai-judge-module-a"' "$OUT_JSON"
expect_contains "json includes p5 module" '"module":"ai-judge-p5-calibration-prep"' "$OUT_JSON"
expect_contains "json includes on-env debt" '"debt":"ai-judge-p5-real-calibration-on-env"' "$OUT_JSON"

expect_contains "markdown completed header" "## completed.md Candidate Rows" "$OUT_MD"
expect_contains "markdown todo header" "## todo.md Candidate Rows" "$OUT_MD"
expect_contains "markdown includes delayed reason" "真实压测样本不足" "$OUT_MD"

echo "all ai-judge stage closure draft tests passed"
