#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
SCRIPT="$ROOT/scripts/release/supply_chain_allowlist_expiry_check.sh"

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

CARGO_FAR="$TMP_DIR/cargo.far.csv"
PIP_FAR="$TMP_DIR/pip.far.csv"

cat >"$CARGO_FAR" <<'EOF_CARGO_FAR'
# advisory_id,target,expires_on,owner,reason
RUSTSEC-2099-0001,chat,2099-12-31,security-team,test far future
EOF_CARGO_FAR

cat >"$PIP_FAR" <<'EOF_PIP_FAR'
# vuln_id,package,expires_on,owner,reason
GHSA-future-0001-0001,fastapi,2099-12-31,security-team,test far future
EOF_PIP_FAR

expect_pass "far future allowlists should pass" \
  "$SCRIPT" \
    --cargo-advisory-allowlist "$CARGO_FAR" \
    --pip-audit-allowlist "$PIP_FAR" \
    --warning-days 7 \
    --report-out "$TMP_DIR/report.pass.far.md"

CARGO_WARN="$TMP_DIR/cargo.warn.csv"
PIP_WARN="$TMP_DIR/pip.warn.csv"

cat >"$CARGO_WARN" <<'EOF_CARGO_WARN'
# advisory_id,target,expires_on,owner,reason
RUSTSEC-2099-0002,chat,2099-12-31,security-team,test far future
EOF_CARGO_WARN

cat >"$PIP_WARN" <<'EOF_PIP_WARN'
# vuln_id,package,expires_on,owner,reason
GHSA-warn-0001-0001,fastapi,2099-12-31,security-team,test near warning by threshold
EOF_PIP_WARN

expect_pass "warning only should pass by default" \
  "$SCRIPT" \
    --cargo-advisory-allowlist "$CARGO_WARN" \
    --pip-audit-allowlist "$PIP_WARN" \
    --warning-days 40000 \
    --report-out "$TMP_DIR/report.pass.warn.md"

expect_fail "warning should fail when fail-on-warning enabled" \
  "$SCRIPT" \
    --cargo-advisory-allowlist "$CARGO_WARN" \
    --pip-audit-allowlist "$PIP_WARN" \
    --warning-days 40000 \
    --fail-on-warning \
    --report-out "$TMP_DIR/report.fail.warn.md"

CARGO_EXPIRED="$TMP_DIR/cargo.expired.csv"
PIP_EXPIRED="$TMP_DIR/pip.expired.csv"
cat >"$CARGO_EXPIRED" <<'EOF_CARGO_EXPIRED'
# advisory_id,target,expires_on,owner,reason
RUSTSEC-2099-0003,chat,2020-01-01,security-team,test expired
EOF_CARGO_EXPIRED
cat >"$PIP_EXPIRED" <<'EOF_PIP_EXPIRED'
# vuln_id,package,expires_on,owner,reason
GHSA-expired-0001-0001,fastapi,2020-01-01,security-team,test expired
EOF_PIP_EXPIRED

expect_fail "expired rows should fail" \
  "$SCRIPT" \
    --cargo-advisory-allowlist "$CARGO_EXPIRED" \
    --pip-audit-allowlist "$PIP_EXPIRED" \
    --warning-days 7 \
    --report-out "$TMP_DIR/report.fail.expired.md"

CARGO_INVALID_DATE="$TMP_DIR/cargo.invalid-date.csv"
cat >"$CARGO_INVALID_DATE" <<'EOF_CARGO_INVALID_DATE'
# advisory_id,target,expires_on,owner,reason
RUSTSEC-2099-0004,chat,2099/12/31,security-team,test invalid date format
EOF_CARGO_INVALID_DATE

expect_fail "invalid expires_on should fail" \
  "$SCRIPT" \
    --cargo-advisory-allowlist "$CARGO_INVALID_DATE" \
    --pip-audit-allowlist "$PIP_FAR" \
    --report-out "$TMP_DIR/report.fail.invalid-date.md"

expect_fail "missing allowlist files should fail" \
  "$SCRIPT" \
    --cargo-advisory-allowlist "$TMP_DIR/not-exists-cargo.csv" \
    --pip-audit-allowlist "$TMP_DIR/not-exists-pip.csv" \
    --report-out "$TMP_DIR/report.fail.missing.md"

echo "all supply chain allowlist expiry check tests passed"
