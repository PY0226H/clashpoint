#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)"
SCRIPT="$ROOT/skills/pre-module-prd-goal-guard/scripts/run_prd_goal_guard.sh"

TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

expect_contains() {
  local name="$1"
  local pattern="$2"
  local file="$3"
  if grep -Fq -- "$pattern" "$file"; then
    echo "[PASS] $name"
    return 0
  fi
  echo "[FAIL] $name: missing pattern '$pattern'"
  echo "--- output ---"
  cat "$file"
  exit 1
}

SUMMARY_OUT="$TMP_DIR/summary.out"
SUMMARY_META="$TMP_DIR/summary.meta"
bash "$SCRIPT" \
  --root "$ROOT" \
  --task-kind dev \
  --module docs-navigation \
  --summary "sync docs navigation wording" \
  --mode auto \
  --metadata-out "$SUMMARY_META" \
  --dry-run >"$SUMMARY_OUT"

expect_contains "auto mode defaults to summary" "prd_mode_effective: summary" "$SUMMARY_OUT"
expect_contains "summary metadata keeps digest only" "evidence_paths=$ROOT/docs/harness/product-goals.md" "$SUMMARY_META"

FULL_OUT="$TMP_DIR/full.out"
FULL_META="$TMP_DIR/full.meta"
bash "$SCRIPT" \
  --root "$ROOT" \
  --task-kind dev \
  --module auth-session-hardening \
  --summary "tighten signin token and sms verification flow" \
  --mode auto \
  --metadata-out "$FULL_META" \
  --dry-run >"$FULL_OUT"

expect_contains "auth keyword escalates to full" "prd_mode_effective: full" "$FULL_OUT"
expect_contains "auth keyword reason is printed" "full_prd_reason: 命中高风险认证/权限关键词: auth" "$FULL_OUT"
expect_contains "full metadata includes authority prd" "evidence_paths=$ROOT/docs/harness/product-goals.md;$ROOT/docs/PRD/在线辩论AI裁判平台完整PRD.md" "$FULL_META"

FORCED_OUT="$TMP_DIR/forced.out"
bash "$SCRIPT" \
  --root "$ROOT" \
  --task-kind refactor \
  --module lobby-cleanup \
  --summary "cleanup lobby orchestration" \
  --mode full \
  --dry-run >"$FORCED_OUT"

expect_contains "forced full mode respected" "prd_mode_effective: full" "$FORCED_OUT"
expect_contains "forced full reason printed" "full_prd_reason: 显式指定 --mode full" "$FORCED_OUT"

echo "all prd guard tests passed"
