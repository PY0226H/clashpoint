#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
SCRIPT="$ROOT/scripts/harness/ai_judge_real_pass_rehearsal.sh"

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

WORKSPACE="$TMP_DIR/rehearsal-workspace"
STDOUT_FILE="$TMP_DIR/rehearsal.stdout"
OUT_ENV="$TMP_DIR/rehearsal.env"
OUT_DOC="$TMP_DIR/rehearsal.md"
OUT_JSON="$TMP_DIR/rehearsal.summary.json"
OUT_MD="$TMP_DIR/rehearsal.summary.md"

bash "$SCRIPT" \
  --root "$ROOT" \
  --workspace-root "$WORKSPACE" \
  --output-env "$OUT_ENV" \
  --output-doc "$OUT_DOC" \
  --emit-json "$OUT_JSON" \
  --emit-md "$OUT_MD" >"$STDOUT_FILE"

expect_contains "stdout status pass" "ai_judge_real_pass_rehearsal_status: pass" "$STDOUT_FILE"
expect_contains "stdout window pass" "window_status: pass" "$STDOUT_FILE"
expect_contains "stdout ready true" "window_real_pass_ready: true" "$STDOUT_FILE"

expect_contains "env status pass" "AI_JUDGE_REAL_PASS_REHEARSAL_STATUS=pass" "$OUT_ENV"
expect_contains "env window pass" "WINDOW_CLOSURE_STATUS=pass" "$OUT_ENV"
expect_contains "env real pass ready" "WINDOW_REAL_PASS_READY=true" "$OUT_ENV"

WINDOW_ENV="$WORKSPACE/docs/loadtest/evidence/ai_judge_real_env_window_closure.env"
expect_contains "workspace window env exists" "AI_JUDGE_REAL_ENV_WINDOW_CLOSURE_STATUS=pass" "$WINDOW_ENV"
expect_contains "workspace window real pass ready" "REAL_PASS_READY=true" "$WINDOW_ENV"

expect_contains "json pass" "\"status\": \"pass\"" "$OUT_JSON"
expect_contains "json window pass" "\"status\": \"pass\"" "$OUT_JSON"
expect_contains "md title" "# ai-judge-real-pass-rehearsal" "$OUT_MD"

echo "all ai-judge real pass rehearsal tests passed"
