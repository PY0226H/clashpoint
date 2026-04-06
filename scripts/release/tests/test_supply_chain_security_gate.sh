#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
SCRIPT="$ROOT/scripts/release/supply_chain_security_gate.sh"

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
  "$FAKE_ROOT/ai_judge_service"

cat >"$FAKE_ROOT/ai_judge_service/requirements.txt" <<'EOF_REQUIREMENTS'
fastapi==0.116.1
EOF_REQUIREMENTS

cat >"$FAKE_ROOT/chat/deny.toml" <<'EOF_DENY_CHAT'
[advisories]
ignore = []
EOF_DENY_CHAT

cat >"$FAKE_ROOT/frontend/apps/desktop/src-tauri/deny.toml" <<'EOF_DENY_CHATAPP'
[advisories]
ignore = ["RUSTSEC-2024-0001"]
EOF_DENY_CHATAPP

cat >"$FAKE_ROOT/swiftide-pgvector/deny.toml" <<'EOF_DENY_SWIFTIDE'
[advisories]
ignore = []
EOF_DENY_SWIFTIDE

CARGO_ALLOWLIST_OK="$TMP_DIR/cargo_allowlist.ok.csv"
CARGO_ALLOWLIST_EMPTY="$TMP_DIR/cargo_allowlist.empty.csv"
CARGO_ALLOWLIST_EXPIRED="$TMP_DIR/cargo_allowlist.expired.csv"
PIP_ALLOWLIST_EMPTY="$TMP_DIR/pip_allowlist.empty.csv"
PIP_ALLOWLIST_EXPIRED="$TMP_DIR/pip_allowlist.expired.csv"

cat >"$CARGO_ALLOWLIST_OK" <<'EOF_CARGO_OK'
# advisory_id,target,expires_on,owner,reason
RUSTSEC-2024-0001,frontend/apps/desktop/src-tauri,2099-12-31,security-team,temporary waiver for test
EOF_CARGO_OK

cat >"$CARGO_ALLOWLIST_EMPTY" <<'EOF_CARGO_EMPTY'
# advisory_id,target,expires_on,owner,reason
EOF_CARGO_EMPTY

cat >"$CARGO_ALLOWLIST_EXPIRED" <<'EOF_CARGO_EXPIRED'
# advisory_id,target,expires_on,owner,reason
RUSTSEC-2024-0001,frontend/apps/desktop/src-tauri,2020-01-01,security-team,expired waiver for test
EOF_CARGO_EXPIRED

cat >"$PIP_ALLOWLIST_EMPTY" <<'EOF_PIP_EMPTY'
# vuln_id,package,expires_on,owner,reason
EOF_PIP_EMPTY

cat >"$PIP_ALLOWLIST_EXPIRED" <<'EOF_PIP_EXPIRED'
# vuln_id,package,expires_on,owner,reason
GHSA-xxxx-yyyy-zzzz,fastapi,2020-01-01,security-team,expired waiver for test
EOF_PIP_EXPIRED

BIN_DIR="$TMP_DIR/bin"
mkdir -p "$BIN_DIR"

cat >"$BIN_DIR/cargo-audit" <<'EOF_CARGO_AUDIT'
#!/usr/bin/env bash
set -euo pipefail
if [[ -n "${FAIL_AUDIT_TARGET:-}" && "$PWD" == *"${FAIL_AUDIT_TARGET}"* ]]; then
  echo "mock cargo-audit fail at $PWD" >&2
  exit 1
fi
echo "mock cargo-audit pass at $PWD"
EOF_CARGO_AUDIT
chmod +x "$BIN_DIR/cargo-audit"

cat >"$BIN_DIR/cargo-deny" <<'EOF_CARGO_DENY'
#!/usr/bin/env bash
set -euo pipefail
if [[ -n "${FAIL_DENY_TARGET:-}" && "$PWD" == *"${FAIL_DENY_TARGET}"* ]]; then
  echo "mock cargo-deny fail at $PWD" >&2
  exit 1
fi
echo "mock cargo-deny pass at $PWD"
EOF_CARGO_DENY
chmod +x "$BIN_DIR/cargo-deny"

cat >"$BIN_DIR/python-mock" <<'EOF_PYTHON_MOCK'
#!/usr/bin/env bash
set -euo pipefail
if [[ "$#" -ge 2 && "$1" == "-m" && "$2" == "pip_audit" ]]; then
  if [[ "${MISSING_PIP_AUDIT:-0}" == "1" ]]; then
    echo "No module named pip_audit" >&2
    exit 1
  fi
  if [[ "${FAIL_PIP_AUDIT:-0}" == "1" ]]; then
    echo "mock pip-audit found vulnerabilities" >&2
    exit 1
  fi
  echo "mock pip-audit pass"
  exit 0
fi
echo "unexpected args: $*" >&2
exit 2
EOF_PYTHON_MOCK
chmod +x "$BIN_DIR/python-mock"

expect_pass "all tools pass should pass gate" \
  env \
    FAIL_AUDIT_TARGET="" \
    FAIL_DENY_TARGET="" \
    FAIL_PIP_AUDIT="0" \
    MISSING_PIP_AUDIT="0" \
  "$SCRIPT" \
    --root "$FAKE_ROOT" \
    --cargo-audit-bin "$BIN_DIR/cargo-audit" \
    --cargo-deny-bin "$BIN_DIR/cargo-deny" \
    --cargo-advisory-allowlist "$CARGO_ALLOWLIST_OK" \
    --python-bin "$BIN_DIR/python-mock" \
    --python-requirements "$FAKE_ROOT/ai_judge_service/requirements.txt" \
    --pip-audit-allowlist "$PIP_ALLOWLIST_EMPTY" \
    --report-out "$TMP_DIR/report.pass.md"

if [[ ! -f "$TMP_DIR/report.pass.md" ]]; then
  echo "[FAIL] pass case should generate report"
  exit 1
fi

expect_fail "cargo-audit fail should fail gate" \
  env \
    FAIL_AUDIT_TARGET="frontend/apps/desktop/src-tauri" \
    FAIL_DENY_TARGET="" \
    FAIL_PIP_AUDIT="0" \
    MISSING_PIP_AUDIT="0" \
  "$SCRIPT" \
    --root "$FAKE_ROOT" \
    --cargo-audit-bin "$BIN_DIR/cargo-audit" \
    --cargo-deny-bin "$BIN_DIR/cargo-deny" \
    --cargo-advisory-allowlist "$CARGO_ALLOWLIST_OK" \
    --python-bin "$BIN_DIR/python-mock" \
    --python-requirements "$FAKE_ROOT/ai_judge_service/requirements.txt" \
    --pip-audit-allowlist "$PIP_ALLOWLIST_EMPTY" \
    --report-out "$TMP_DIR/report.fail.audit.md"

expect_fail "missing tool without allow flag should fail" \
  "$SCRIPT" \
    --root "$FAKE_ROOT" \
    --cargo-audit-bin "$BIN_DIR/not-exists-audit" \
    --cargo-deny-bin "$BIN_DIR/cargo-deny" \
    --cargo-advisory-allowlist "$CARGO_ALLOWLIST_OK" \
    --python-bin "$BIN_DIR/python-mock" \
    --python-requirements "$FAKE_ROOT/ai_judge_service/requirements.txt" \
    --pip-audit-allowlist "$PIP_ALLOWLIST_EMPTY" \
    --report-out "$TMP_DIR/report.fail.missing-tool.md"

expect_pass "missing tool with allow flag should pass with warnings" \
  "$SCRIPT" \
    --root "$FAKE_ROOT" \
    --allow-missing-tools \
    --cargo-audit-bin "$BIN_DIR/not-exists-audit" \
    --cargo-deny-bin "$BIN_DIR/not-exists-deny" \
    --cargo-advisory-allowlist "$CARGO_ALLOWLIST_OK" \
    --python-bin "$BIN_DIR/not-exists-python" \
    --python-requirements "$FAKE_ROOT/ai_judge_service/requirements.txt" \
    --pip-audit-allowlist "$PIP_ALLOWLIST_EMPTY" \
    --report-out "$TMP_DIR/report.pass.allow-missing.md"

expect_fail "cargo allowlist missing metadata should fail" \
  "$SCRIPT" \
    --root "$FAKE_ROOT" \
    --cargo-audit-bin "$BIN_DIR/cargo-audit" \
    --cargo-deny-bin "$BIN_DIR/cargo-deny" \
    --cargo-advisory-allowlist "$CARGO_ALLOWLIST_EMPTY" \
    --python-bin "$BIN_DIR/python-mock" \
    --python-requirements "$FAKE_ROOT/ai_judge_service/requirements.txt" \
    --pip-audit-allowlist "$PIP_ALLOWLIST_EMPTY" \
    --report-out "$TMP_DIR/report.fail.cargo-missing-metadata.md"

expect_fail "expired cargo allowlist row should fail" \
  "$SCRIPT" \
    --root "$FAKE_ROOT" \
    --cargo-audit-bin "$BIN_DIR/cargo-audit" \
    --cargo-deny-bin "$BIN_DIR/cargo-deny" \
    --cargo-advisory-allowlist "$CARGO_ALLOWLIST_EXPIRED" \
    --python-bin "$BIN_DIR/python-mock" \
    --python-requirements "$FAKE_ROOT/ai_judge_service/requirements.txt" \
    --pip-audit-allowlist "$PIP_ALLOWLIST_EMPTY" \
    --report-out "$TMP_DIR/report.fail.cargo-expired.md"

expect_fail "expired pip allowlist row should fail" \
  "$SCRIPT" \
    --root "$FAKE_ROOT" \
    --cargo-audit-bin "$BIN_DIR/cargo-audit" \
    --cargo-deny-bin "$BIN_DIR/cargo-deny" \
    --cargo-advisory-allowlist "$CARGO_ALLOWLIST_OK" \
    --python-bin "$BIN_DIR/python-mock" \
    --python-requirements "$FAKE_ROOT/ai_judge_service/requirements.txt" \
    --pip-audit-allowlist "$PIP_ALLOWLIST_EXPIRED" \
    --report-out "$TMP_DIR/report.fail.pip-expired.md"

echo "all supply chain security gate tests passed"
