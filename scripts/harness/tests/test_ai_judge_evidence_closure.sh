#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
SCRIPT="$ROOT/scripts/harness/ai_judge_evidence_closure.sh"

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

seed_module_summary() {
  local base="$1"
  local module="$2"
  local ts="$3"
  local json_path="$base/artifacts/harness/${ts}-${module}.summary.json"
  local md_path="$base/artifacts/harness/${ts}-${module}.summary.md"
  cat >"$json_path" <<JSON
{"module":"$module","status":"pass"}
JSON
  cat >"$md_path" <<MD
# $module
status: pass
MD
}

WORK_PASS="$TMP_DIR/pass-root"
mkdir -p "$WORK_PASS/artifacts/harness"

seed_module_summary "$WORK_PASS" "ai-judge-p2-judge-mainline-migration" "20260413T120001Z"
seed_module_summary "$WORK_PASS" "ai-judge-p2-phase-mainline-migration" "20260413T120002Z"
seed_module_summary "$WORK_PASS" "ai-judge-p3-replay-audit-ops-convergence" "20260413T120003Z"
seed_module_summary "$WORK_PASS" "ai-judge-p4-agent-runtime-shell" "20260413T120004Z"
seed_module_summary "$WORK_PASS" "ai-judge-runtime-verify-closure" "20260413T120005Z"

PASS_STDOUT="$TMP_DIR/pass.stdout"
PASS_JSON="$TMP_DIR/pass.summary.json"
PASS_MD="$TMP_DIR/pass.summary.md"

bash "$SCRIPT" \
  --root "$WORK_PASS" \
  --emit-json "$PASS_JSON" \
  --emit-md "$PASS_MD" >"$PASS_STDOUT"

expect_contains "pass stdout status" "ai_judge_evidence_status: pass" "$PASS_STDOUT"
expect_contains "pass json status" "\"status\": \"pass\"" "$PASS_JSON"
expect_contains "pass json missing count" "\"missing_total\": 0" "$PASS_JSON"
expect_contains "pass markdown contains table" "## Module Coverage" "$PASS_MD"
expect_contains "pass markdown contains no missing" "- （无）" "$PASS_MD"

WORK_MISSING="$TMP_DIR/missing-root"
mkdir -p "$WORK_MISSING/artifacts/harness"

seed_module_summary "$WORK_MISSING" "ai-judge-p2-judge-mainline-migration" "20260413T130001Z"
seed_module_summary "$WORK_MISSING" "ai-judge-p2-phase-mainline-migration" "20260413T130002Z"
seed_module_summary "$WORK_MISSING" "ai-judge-p3-replay-audit-ops-convergence" "20260413T130003Z"
seed_module_summary "$WORK_MISSING" "ai-judge-p4-agent-runtime-shell" "20260413T130004Z"

MISSING_STDOUT="$TMP_DIR/missing.stdout"
MISSING_JSON="$TMP_DIR/missing.summary.json"
MISSING_MD="$TMP_DIR/missing.summary.md"

bash "$SCRIPT" \
  --root "$WORK_MISSING" \
  --emit-json "$MISSING_JSON" \
  --emit-md "$MISSING_MD" >"$MISSING_STDOUT"

expect_contains "missing stdout status" "ai_judge_evidence_status: evidence_missing" "$MISSING_STDOUT"
expect_contains "missing json status" "\"status\": \"evidence_missing\"" "$MISSING_JSON"
expect_contains "missing json module" "ai-judge-runtime-verify-closure" "$MISSING_JSON"
expect_contains "missing markdown module" "- ai-judge-runtime-verify-closure" "$MISSING_MD"

echo "all ai-judge evidence closure tests passed"
