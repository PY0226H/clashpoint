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

expect_not_contains() {
  local name="$1"
  local pattern="$2"
  local file="$3"
  if ! grep -Fq -- "$pattern" "$file"; then
    echo "[PASS] $name"
    return
  fi
  echo "[FAIL] $name: unexpected pattern '$pattern'"
  echo "--- output ---"
  cat "$file"
  exit 1
}

DEV_OUT="$TMP_DIR/dev.out"
bash "$SCRIPT" \
  --root "$ROOT" \
  --task-kind dev \
  --module ai-judge-p36-artifact-store-port-local-pack \
  --summary "Add local artifact store port and adapter for AI Judge trust and audit artifacts" >"$DEV_OUT"

expect_contains "dev output includes recommended label" "Recommended:" "$DEV_OUT"
expect_contains "dev output uses concise ai-judge scope" "feat(ai-judge): add local artifact store adapter" "$DEV_OUT"
expect_not_contains "dev output avoids long module scope" "(ai-judge-p36-artifact-store-port-local-pack):" "$DEV_OUT"
expect_not_contains "dev output avoids mechanical subject" "advance ai-judge-p36-artifact-store-port-local-pack workflow" "$DEV_OUT"
expect_contains "dev output includes alternatives" "Alternatives:" "$DEV_OUT"

ROUTE_OUT="$TMP_DIR/route.out"
bash "$SCRIPT" \
  --root "$ROOT" \
  --task-kind dev \
  --module ai-judge-p36-route-dependency-hotspot-split-pack \
  --summary "Split AI Judge trust and ops route dependency assembly out of app_factory without changing route behavior" >"$ROUTE_OUT"

expect_contains "route split uses refactor type" "refactor(ai-judge): split trust and ops route wiring" "$ROUTE_OUT"
expect_not_contains "route split avoids generic capability subject" "add ai-judge capability" "$ROUTE_OUT"
expect_not_contains "route split avoids sync follow-up alternative" "sync ai-judge follow-up" "$ROUTE_OUT"

LOCAL_REF_OUT="$TMP_DIR/local-reference.out"
bash "$SCRIPT" \
  --root "$ROOT" \
  --task-kind dev \
  --module ai-judge-p36-local-reference-regression-pack \
  --summary "Record P36 AI Judge local reference regression evidence and runtime ops pack status without claiming real environment pass" >"$LOCAL_REF_OUT"

expect_contains "local reference uses docs type" "docs(ai-judge): record p36 local reference evidence" "$LOCAL_REF_OUT"
expect_not_contains "local reference avoids generic capability subject" "add ai-judge capability" "$LOCAL_REF_OUT"
expect_not_contains "local reference avoids sync follow-up alternative" "sync ai-judge follow-up" "$LOCAL_REF_OUT"

TITLE_OUT="$TMP_DIR/title.out"
bash "$SCRIPT" \
  --root "$ROOT" \
  --task-kind refactor \
  --module post-module-commit-message-humanized-output \
  --summary "Tune post-module commit message skill to prefer concise human commit messages" \
  --title-only >"$TITLE_OUT"

expect_contains "title-only uses concise refactor title" "refactor(commit-message): improve commit message recommendations" "$TITLE_OUT"
expect_not_contains "title-only avoids long commit-message module scope" "(post-module-commit-message-humanized-output):" "$TITLE_OUT"

echo "all post-module-commit-message script tests passed"
