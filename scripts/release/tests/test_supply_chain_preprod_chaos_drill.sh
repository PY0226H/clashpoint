#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
SCRIPT="$ROOT/scripts/release/supply_chain_preprod_chaos_drill.sh"

if [[ ! -x "$SCRIPT" ]]; then
  chmod +x "$SCRIPT"
fi

TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

expect_fail() {
  local name="$1"
  shift
  if "$@" >/dev/null 2>&1; then
    echo "[FAIL] $name: expected failure but passed"
    exit 1
  fi
  echo "[PASS] $name"
}

expect_pass() {
  local name="$1"
  shift
  if "$@" >/dev/null 2>&1; then
    echo "[PASS] $name"
    return
  fi
  echo "[FAIL] $name: expected pass but failed"
  exit 1
}

FAKE_ROOT="$TMP_DIR/root"
mkdir -p \
  "$FAKE_ROOT/chat" \
  "$FAKE_ROOT/frontend/apps/desktop/src-tauri" \
  "$FAKE_ROOT/swiftide-pgvector" \
  "$FAKE_ROOT/ai_judge_service" \
  "$FAKE_ROOT/scripts/release/security_allowlists"

cat >"$FAKE_ROOT/chat/deny.toml" <<'EOF_DENY_CHAT'
[advisories]
ignore = []
EOF_DENY_CHAT

cat >"$FAKE_ROOT/frontend/apps/desktop/src-tauri/deny.toml" <<'EOF_DENY_CHATAPP'
[advisories]
ignore = []
EOF_DENY_CHATAPP

cat >"$FAKE_ROOT/swiftide-pgvector/deny.toml" <<'EOF_DENY_SWIFTIDE'
[advisories]
ignore = []
EOF_DENY_SWIFTIDE

cat >"$FAKE_ROOT/ai_judge_service/requirements.txt" <<'EOF_REQUIREMENTS'
fastapi==0.116.1
EOF_REQUIREMENTS

cat >"$FAKE_ROOT/scripts/release/security_allowlists/cargo_deny_advisories_allowlist.csv" <<'EOF_CARGO_ALLOW'
# advisory_id,target,expires_on,owner,reason
RUSTSEC-2099-0001,chat,2099-12-31,security-team,test row
EOF_CARGO_ALLOW

cat >"$FAKE_ROOT/scripts/release/security_allowlists/pip_audit_vulns_allowlist.csv" <<'EOF_PIP_ALLOW'
# vuln_id,package,expires_on,owner,reason
EOF_PIP_ALLOW

GATE_ALWAYS_FAIL="$TMP_DIR/gate.fail.sh"
cat >"$GATE_ALWAYS_FAIL" <<'EOF_GATE_FAIL'
#!/usr/bin/env bash
set -euo pipefail
exit 1
EOF_GATE_FAIL
chmod +x "$GATE_ALWAYS_FAIL"

GATE_ALWAYS_PASS="$TMP_DIR/gate.pass.sh"
cat >"$GATE_ALWAYS_PASS" <<'EOF_GATE_PASS'
#!/usr/bin/env bash
set -euo pipefail
exit 0
EOF_GATE_PASS
chmod +x "$GATE_ALWAYS_PASS"

EVIDENCE_PASS="$TMP_DIR/evidence.pass.env"
REPORT_PASS="$TMP_DIR/report.pass.md"
expect_pass "chaos drill should pass when gate blocks all scenarios" \
  "$SCRIPT" \
    --root "$FAKE_ROOT" \
    --supply-chain-gate-script "$GATE_ALWAYS_FAIL" \
    --evidence-out "$EVIDENCE_PASS" \
    --report-out "$REPORT_PASS"

if [[ ! -f "$EVIDENCE_PASS" ]]; then
  echo "[FAIL] evidence file should be generated"
  exit 1
fi

grep -q '^SCENARIO_ADVISORY_SOURCE_UNAVAILABLE=pass$' "$EVIDENCE_PASS" || {
  echo "[FAIL] advisory scenario should be pass in evidence"
  exit 1
}
grep -q '^SCENARIO_PIP_AUDIT_MISSING=pass$' "$EVIDENCE_PASS" || {
  echo "[FAIL] pip scenario should be pass in evidence"
  exit 1
}
grep -q '^SCENARIO_ALLOWLIST_EXPIRED=pass$' "$EVIDENCE_PASS" || {
  echo "[FAIL] allowlist scenario should be pass in evidence"
  exit 1
}

expect_fail "chaos drill should fail when gate passes all scenarios" \
  "$SCRIPT" \
    --root "$FAKE_ROOT" \
    --supply-chain-gate-script "$GATE_ALWAYS_PASS" \
    --evidence-out "$TMP_DIR/evidence.fail.env" \
    --report-out "$TMP_DIR/report.fail.md"

echo "all supply chain preprod chaos drill tests passed"
