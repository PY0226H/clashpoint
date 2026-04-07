#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
SCRIPT="$ROOT/scripts/harness/journey_verify.sh"

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

AUTH_STDOUT="$TMP_DIR/auth.stdout"
AUTH_JSON="$TMP_DIR/auth.summary.json"
AUTH_MD="$TMP_DIR/auth.summary.md"

bash "$SCRIPT" \
  --root "$ROOT" \
  --profile auth \
  --emit-json "$AUTH_JSON" \
  --emit-md "$AUTH_MD" >"$AUTH_STDOUT"

if [[ ! -f "$AUTH_JSON" || ! -f "$AUTH_MD" ]]; then
  echo "[FAIL] auth profile should emit summary files"
  exit 1
fi

expect_contains "auth stdout exposes status" "journey_verify_status: evidence_missing" "$AUTH_STDOUT"
expect_contains "auth stdout exposes profile" "journey_verify_profile: auth" "$AUTH_STDOUT"
expect_contains "auth json records profile" "\"profile\": \"auth\"" "$AUTH_JSON"
expect_contains "auth json records phase owner" "\"phase_owner\": \"P3-2\"" "$AUTH_JSON"
expect_contains "auth json records dispatcher check" "\"check_id\":\"profile-dispatch\"" "$AUTH_JSON"
expect_contains "auth json marks missing evidence" "\"status\":\"evidence_missing\"" "$AUTH_JSON"
expect_contains "auth markdown has checks section" "## Checks" "$AUTH_MD"
expect_contains "auth markdown mentions auth smoke" "认证 smoke（web）" "$AUTH_MD"

RELEASE_STDOUT="$TMP_DIR/release.stdout"
RELEASE_JSON="$TMP_DIR/release.summary.json"
RELEASE_MD="$TMP_DIR/release.summary.md"

bash "$SCRIPT" \
  --root "$ROOT" \
  --profile release \
  --emit-json "$RELEASE_JSON" \
  --emit-md "$RELEASE_MD" \
  --collect-logs \
  --collect-metrics \
  --collect-trace >"$RELEASE_STDOUT"

expect_contains "release stdout exposes missing evidence" "journey_verify_status: evidence_missing" "$RELEASE_STDOUT"
expect_contains "release json records collector request" "\"logs\": true" "$RELEASE_JSON"
expect_contains "release json records supply chain source" "supply_chain_security_gate.sh" "$RELEASE_JSON"
expect_contains "release markdown has collectors table" "## Collectors" "$RELEASE_MD"

INVALID_STDOUT="$TMP_DIR/invalid.stdout"
set +e
bash "$SCRIPT" \
  --root "$ROOT" \
  --profile unknown >"$INVALID_STDOUT" 2>&1
RC=$?
set -e

if [[ "$RC" -eq 0 ]]; then
  echo "[FAIL] unsupported profile should fail"
  exit 1
fi
expect_contains "invalid profile prints reason" "不支持的 profile: unknown" "$INVALID_STDOUT"

echo "all journey-verify tests passed"
