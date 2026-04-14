#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
SCRIPT="$ROOT/scripts/harness/ai_judge_fairness_gate_bootstrap.sh"

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

WORK_ROOT="$TMP_DIR/work-root"
mkdir -p "$WORK_ROOT/docs/dev_plan" "$WORK_ROOT/docs/loadtest/evidence" "$WORK_ROOT/artifacts/harness"

OUT_DOC="$WORK_ROOT/docs/dev_plan/fairness_gate_bootstrap.md"
OUT_ENV="$WORK_ROOT/docs/loadtest/evidence/fairness_gate_bootstrap.env"
OUT_JSON="$TMP_DIR/bootstrap.summary.json"
OUT_MD="$TMP_DIR/bootstrap.summary.md"
OUT_STDOUT="$TMP_DIR/bootstrap.stdout"

bash "$SCRIPT" \
  --root "$WORK_ROOT" \
  --output-doc "$OUT_DOC" \
  --output-env "$OUT_ENV" \
  --emit-json "$OUT_JSON" \
  --emit-md "$OUT_MD" >"$OUT_STDOUT"

expect_contains "stdout status" "ai_judge_fairness_gate_bootstrap_status: pass" "$OUT_STDOUT"
expect_contains "stdout output doc" "output_doc: $OUT_DOC" "$OUT_STDOUT"
expect_contains "doc title" "# AI Judge Fairness Gate 执行蓝图" "$OUT_DOC"
expect_contains "doc fg1" "### FG-1 label swap instability" "$OUT_DOC"
expect_contains "doc fg2" "### FG-2 style perturbation instability" "$OUT_DOC"
expect_contains "doc fg3" "### FG-3 panel disagreement gate" "$OUT_DOC"
expect_contains "env status" "FAIRNESS_GATE_BOOTSTRAP_STATUS=prepared" "$OUT_ENV"
expect_contains "env real req" "REAL_ENV_REQUIRED_FOR_BOOTSTRAP=false" "$OUT_ENV"
expect_contains "json status" '"status": "pass"' "$OUT_JSON"
expect_contains "md title" "# AI Judge Fairness Gate Bootstrap" "$OUT_MD"

# 二次执行确保幂等覆盖
SECOND_STDOUT="$TMP_DIR/bootstrap.second.stdout"
bash "$SCRIPT" \
  --root "$WORK_ROOT" \
  --output-doc "$OUT_DOC" \
  --output-env "$OUT_ENV" \
  --emit-json "$OUT_JSON" \
  --emit-md "$OUT_MD" >"$SECOND_STDOUT"

expect_contains "second stdout status" "ai_judge_fairness_gate_bootstrap_status: pass" "$SECOND_STDOUT"
expect_contains "doc still fg3" "### FG-3 panel disagreement gate" "$OUT_DOC"

echo "all ai-judge fairness gate bootstrap tests passed"
