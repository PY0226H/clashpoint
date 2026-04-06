#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
SCRIPT="$ROOT/scripts/release/supply_chain_sbom_attestation.sh"

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

cat >"$FAKE_ROOT/chat/Cargo.lock" <<'EOF_LOCK_CHAT'
[[package]]
name = "chat-server"
version = "0.1.0"
source = "registry+https://github.com/rust-lang/crates.io-index"
EOF_LOCK_CHAT

cat >"$FAKE_ROOT/frontend/apps/desktop/src-tauri/Cargo.lock" <<'EOF_LOCK_TAURI'
[[package]]
name = "echoisle-desktop"
version = "0.1.0"
source = "registry+https://github.com/rust-lang/crates.io-index"
EOF_LOCK_TAURI

cat >"$FAKE_ROOT/swiftide-pgvector/Cargo.lock" <<'EOF_LOCK_SWIFTIDE'
[[package]]
name = "swiftide-pgvector"
version = "0.1.0"
source = "registry+https://github.com/rust-lang/crates.io-index"
EOF_LOCK_SWIFTIDE

cat >"$FAKE_ROOT/chat/deny.toml" <<'EOF_DENY_CHAT'
[advisories]
ignore = []
EOF_DENY_CHAT

cat >"$FAKE_ROOT/frontend/apps/desktop/src-tauri/deny.toml" <<'EOF_DENY_TAURI'
[advisories]
ignore = []
EOF_DENY_TAURI

cat >"$FAKE_ROOT/swiftide-pgvector/deny.toml" <<'EOF_DENY_SWIFTIDE'
[advisories]
ignore = []
EOF_DENY_SWIFTIDE

REQ_PINNED="$FAKE_ROOT/ai_judge_service/requirements.txt"
cat >"$REQ_PINNED" <<'EOF_REQ'
fastapi==0.116.1
httpx==0.28.1
EOF_REQ

REQ_UNPINNED="$TMP_DIR/requirements.unpinned.txt"
cat >"$REQ_UNPINNED" <<'EOF_REQ_BAD'
fastapi>=0.116.1
EOF_REQ_BAD

BIN_DIR="$TMP_DIR/bin"
mkdir -p "$BIN_DIR"

cat >"$BIN_DIR/cargo-deny-pass" <<'EOF_DENY_PASS'
#!/usr/bin/env bash
set -euo pipefail
exit 0
EOF_DENY_PASS
chmod +x "$BIN_DIR/cargo-deny-pass"

cat >"$BIN_DIR/cargo-deny-fail" <<'EOF_DENY_FAIL'
#!/usr/bin/env bash
set -euo pipefail
exit 1
EOF_DENY_FAIL
chmod +x "$BIN_DIR/cargo-deny-fail"

cat >"$BIN_DIR/python-mock" <<'EOF_PY'
#!/usr/bin/env bash
set -euo pipefail
if [[ "$#" -ge 4 && "$1" == "-m" && "$2" == "pip" && "$3" == "show" ]]; then
  pkg="$4"
  if [[ "$pkg" == "fastapi" ]]; then
    cat <<'OUT'
Name: fastapi
Version: 0.116.1
License: MIT
OUT
    exit 0
  fi
  if [[ "$pkg" == "httpx" ]]; then
    cat <<'OUT'
Name: httpx
Version: 0.28.1
License: BSD-3-Clause
OUT
    exit 0
  fi
  exit 1
fi
exit 1
EOF_PY
chmod +x "$BIN_DIR/python-mock"

REPORT_PASS="$TMP_DIR/report.pass.md"
RUST_SBOM_PASS="$TMP_DIR/rust.pass.json"
PY_SBOM_PASS="$TMP_DIR/python.pass.json"
LICENSE_PASS="$TMP_DIR/license.pass.env"
EVIDENCE_PASS="$TMP_DIR/evidence.pass.env"

expect_pass "sbom attestation should pass with valid inputs" \
  "$SCRIPT" \
    --root "$FAKE_ROOT" \
    --cargo-deny-bin "$BIN_DIR/cargo-deny-pass" \
    --python-bin "$BIN_DIR/python-mock" \
    --python-requirements "$REQ_PINNED" \
    --report-out "$REPORT_PASS" \
    --rust-sbom-out "$RUST_SBOM_PASS" \
    --python-sbom-out "$PY_SBOM_PASS" \
    --license-attestation-out "$LICENSE_PASS" \
    --evidence-out "$EVIDENCE_PASS"

for expected_file in "$REPORT_PASS" "$RUST_SBOM_PASS" "$PY_SBOM_PASS" "$LICENSE_PASS" "$EVIDENCE_PASS"; do
  if [[ ! -f "$expected_file" ]]; then
    echo "[FAIL] expected output not found: $expected_file"
    exit 1
  fi
done

grep -q '^SBOM_LICENSE_CHECK_RUST=pass$' "$EVIDENCE_PASS" || {
  echo "[FAIL] expected rust license status pass in evidence"
  exit 1
}
grep -q '^SBOM_LICENSE_CHECK_PYTHON_PINNED=pass$' "$EVIDENCE_PASS" || {
  echo "[FAIL] expected python pinned status pass in evidence"
  exit 1
}

expect_fail "sbom attestation should fail when cargo-deny licenses fail" \
  "$SCRIPT" \
    --root "$FAKE_ROOT" \
    --cargo-deny-bin "$BIN_DIR/cargo-deny-fail" \
    --python-bin "$BIN_DIR/python-mock" \
    --python-requirements "$REQ_PINNED" \
    --report-out "$TMP_DIR/report.fail.deny.md" \
    --rust-sbom-out "$TMP_DIR/rust.fail.deny.json" \
    --python-sbom-out "$TMP_DIR/python.fail.deny.json" \
    --license-attestation-out "$TMP_DIR/license.fail.deny.env" \
    --evidence-out "$TMP_DIR/evidence.fail.deny.env"

expect_fail "sbom attestation should fail when requirements are unpinned" \
  "$SCRIPT" \
    --root "$FAKE_ROOT" \
    --cargo-deny-bin "$BIN_DIR/cargo-deny-pass" \
    --python-bin "$BIN_DIR/python-mock" \
    --python-requirements "$REQ_UNPINNED" \
    --report-out "$TMP_DIR/report.fail.unpinned.md" \
    --rust-sbom-out "$TMP_DIR/rust.fail.unpinned.json" \
    --python-sbom-out "$TMP_DIR/python.fail.unpinned.json" \
    --license-attestation-out "$TMP_DIR/license.fail.unpinned.env" \
    --evidence-out "$TMP_DIR/evidence.fail.unpinned.env"

echo "all supply chain sbom attestation tests passed"
