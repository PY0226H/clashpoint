#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
SCRIPT="$ROOT/scripts/harness/ai_judge_evidence_gap_remediation.sh"

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

latest_file_by_name() {
  local dir="$1"
  local name="$2"
  local latest=""
  local file
  while IFS= read -r file; do
    latest="$file"
    break
  done < <(find "$dir" -maxdepth 1 -type f -name "$name" -print 2>/dev/null | sort -r)
  printf '%s' "$latest"
}

WORK_ROOT="$TMP_DIR/work"
mkdir -p "$WORK_ROOT/artifacts/harness" "$WORK_ROOT/docs/dev_plan"

cat >"$WORK_ROOT/docs/dev_plan/当前开发计划.md" <<'PLAN'
### 模块完成同步历史

- 2026-04-13：推进 `module-b`；module-b 从计划历史回填摘要

### 2026-04-13 | module-b（执行增量-1）

1. module-b increment note 1
2. module-b increment note 2
PLAN

cat >"$WORK_ROOT/artifacts/harness/20260413T000000Z-module-a.summary.json" <<'JSON'
{"module":"module-a","status":"pass"}
JSON
cat >"$WORK_ROOT/artifacts/harness/20260413T000000Z-module-a.summary.md" <<'MD'
# module-a
status: pass
MD

STDOUT="$TMP_DIR/remediation.stdout"
RUN_JSON="$TMP_DIR/remediation.summary.json"
RUN_MD="$TMP_DIR/remediation.summary.md"

bash "$SCRIPT" \
  --root "$WORK_ROOT" \
  --modules "module-a;module-b;module-c" \
  --emit-json "$RUN_JSON" \
  --emit-md "$RUN_MD" >"$STDOUT"

expect_contains "stdout status" "ai_judge_evidence_gap_remediation_status: pass" "$STDOUT"
expect_contains "stdout created" "created_total: 2" "$STDOUT"
expect_contains "stdout skipped" "skipped_total: 1" "$STDOUT"
expect_contains "run json action" '"action":"backfilled"' "$RUN_JSON"
expect_contains "run markdown table" "## Module Actions" "$RUN_MD"

MODULE_B_JSON="$(latest_file_by_name "$WORK_ROOT/artifacts/harness" "*-module-b.summary.json")"
MODULE_C_JSON="$(latest_file_by_name "$WORK_ROOT/artifacts/harness" "*-module-c.summary.json")"
MODULE_B_MD="$(latest_file_by_name "$WORK_ROOT/artifacts/harness" "*-module-b.summary.md")"

if [[ -z "$MODULE_B_JSON" || -z "$MODULE_C_JSON" || -z "$MODULE_B_MD" ]]; then
  echo "[FAIL] expected backfilled module artifacts not found"
  ls -la "$WORK_ROOT/artifacts/harness"
  exit 1
fi

expect_contains "module-b summary from plan history" "module-b 从计划历史回填摘要" "$MODULE_B_JSON"
expect_contains "module-c summary fallback" "历史模块证据回填" "$MODULE_C_JSON"
expect_contains "module-b md increment note" "module-b increment note 1" "$MODULE_B_MD"

echo "all ai-judge evidence gap remediation tests passed"
