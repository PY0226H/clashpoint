#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
SCRIPT="$ROOT/scripts/harness/ai_judge_artifact_prune.sh"

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

WORK="$TMP_DIR/work"
ARTIFACTS="$WORK/artifacts/harness"
mkdir -p "$ARTIFACTS"

for ts in 20260401T010101Z 20260402T010101Z 20260403T010101Z; do
  cat >"$ARTIFACTS/${ts}-module-a.summary.json" <<'JSON'
{"status":"pass"}
JSON
  cat >"$ARTIFACTS/${ts}-module-a.summary.md" <<'MD'
# summary
MD
  mkdir -p "$ARTIFACTS/${ts}-module-a"
done

for ts in 20260401T010101Z 20260402T010101Z; do
  cat >"$ARTIFACTS/${ts}-module-b.summary.json" <<'JSON'
{"status":"pass"}
JSON
  cat >"$ARTIFACTS/${ts}-module-b.summary.md" <<'MD'
# summary
MD
  mkdir -p "$ARTIFACTS/${ts}-module-b"
done

# 非时间戳命名产物应被忽略
cat >"$ARTIFACTS/ai_judge_ops_read_model_export.summary.json" <<'JSON'
{"stable":"yes"}
JSON
cat >"$ARTIFACTS/ai_judge_ops_read_model_export.summary.md" <<'MD'
# stable
MD

DRY_STDOUT="$TMP_DIR/dry.stdout"
DRY_JSON="$TMP_DIR/dry.summary.json"
DRY_MD="$TMP_DIR/dry.summary.md"
bash "$SCRIPT" \
  --root "$WORK" \
  --keep-latest 1 \
  --emit-json "$DRY_JSON" \
  --emit-md "$DRY_MD" >"$DRY_STDOUT"

expect_contains "dry status" "ai_judge_artifact_prune_status: pass_dry_run" "$DRY_STDOUT"
expect_contains "dry file count" "prune_files_count: 6" "$DRY_STDOUT"
expect_contains "dry dir count" "prune_dirs_count: 3" "$DRY_STDOUT"

if [[ ! -f "$ARTIFACTS/20260401T010101Z-module-a.summary.json" ]]; then
  echo "[FAIL] dry run should not delete files"
  exit 1
fi

APPLY_STDOUT="$TMP_DIR/apply.stdout"
bash "$SCRIPT" \
  --root "$WORK" \
  --keep-latest 1 \
  --apply >"$APPLY_STDOUT"

expect_contains "apply status" "ai_judge_artifact_prune_status: pass_applied" "$APPLY_STDOUT"

if [[ -f "$ARTIFACTS/20260401T010101Z-module-a.summary.json" ]]; then
  echo "[FAIL] old module-a json should be pruned"
  exit 1
fi
if [[ -f "$ARTIFACTS/20260401T010101Z-module-b.summary.json" ]]; then
  echo "[FAIL] old module-b json should be pruned"
  exit 1
fi
if [[ ! -f "$ARTIFACTS/20260403T010101Z-module-a.summary.json" ]]; then
  echo "[FAIL] latest module-a json should be kept"
  exit 1
fi
if [[ ! -f "$ARTIFACTS/20260402T010101Z-module-b.summary.json" ]]; then
  echo "[FAIL] latest module-b json should be kept"
  exit 1
fi
if [[ ! -f "$ARTIFACTS/ai_judge_ops_read_model_export.summary.json" ]]; then
  echo "[FAIL] non timestamp summary json should stay"
  exit 1
fi
if [[ ! -d "$ARTIFACTS/20260403T010101Z-module-a" ]]; then
  echo "[FAIL] latest module-a dir should stay"
  exit 1
fi
if [[ -d "$ARTIFACTS/20260401T010101Z-module-a" ]]; then
  echo "[FAIL] old module-a dir should be pruned"
  exit 1
fi

echo "all ai_judge_artifact_prune tests passed"

