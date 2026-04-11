#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)"
SCRIPT="$ROOT/skills/post-module-commit-message/scripts/recommend_commit_message.sh"
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
  --module harness-commit-skill-integration \
  --summary "让 module-turn-harness 复用 post-module-commit-message skill 输出 commit 推荐" >"$DEV_OUT"

expect_contains "dev output includes recommended label" "Recommended:" "$DEV_OUT"
expect_contains "dev output includes harness scope" "(harness-commit-skill-integration):" "$DEV_OUT"
expect_contains "dev output includes alternatives" "Alternatives:" "$DEV_OUT"

TITLE_OUT="$TMP_DIR/title.out"
bash "$SCRIPT" \
  --root "$ROOT" \
  --task-kind refactor \
  --module auth-session-hardening \
  --summary "refactor auth session flow" \
  --title-only >"$TITLE_OUT"

expect_contains "title-only uses refactor type" "refactor(auth-session-hardening):" "$TITLE_OUT"

echo "all post-module-commit-message script tests passed"
