#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
SCRIPT="$ROOT/scripts/release/appstore_preflight_check.sh"

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

compute_sha256() {
  local file="$1"
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum "$file" | awk '{print $1}'
    return 0
  fi
  shasum -a 256 "$file" | awk '{print $1}'
}

VALID_CHAT="$TMP_DIR/chat.valid.yml"
VALID_TAURI="$TMP_DIR/app.valid.yml"
VALID_AI_ENV="$TMP_DIR/ai.valid.env"
VALID_V2D_REG="$TMP_DIR/v2d.reg.valid.env"
VALID_V2D_LOAD="$TMP_DIR/v2d.load.valid.env"
BAD_V2D_REG="$TMP_DIR/v2d.reg.bad.env"
VALID_M7_REG="$TMP_DIR/m7.reg.valid.env"
VALID_M7_LOAD="$TMP_DIR/m7.load.valid.env"
VALID_M7_FAULT="$TMP_DIR/m7.fault.valid.env"
BAD_M7_FAULT="$TMP_DIR/m7.fault.bad.env"
SUPPLY_GATE_PASS="$TMP_DIR/supply.gate.pass.sh"
SUPPLY_GATE_FAIL="$TMP_DIR/supply.gate.fail.sh"
VALID_SUPPLY_CHAOS="$TMP_DIR/supply.chaos.valid.env"
BAD_SUPPLY_CHAOS="$TMP_DIR/supply.chaos.bad.env"
STALE_SUPPLY_CHAOS="$TMP_DIR/supply.chaos.stale.env"
VALID_SBOM_RUST="$TMP_DIR/sbom.rust.valid.json"
VALID_SBOM_PYTHON="$TMP_DIR/sbom.python.valid.json"
VALID_SBOM_LICENSE="$TMP_DIR/sbom.license.valid.env"
VALID_SBOM_EVIDENCE="$TMP_DIR/sbom.evidence.valid.env"
BAD_SBOM_EVIDENCE_HASH="$TMP_DIR/sbom.evidence.bad.hash.env"
STALE_SBOM_EVIDENCE="$TMP_DIR/sbom.evidence.stale.env"

cat >"$VALID_CHAT" <<'EOF'
payment:
  verify_mode: apple
  apple_verify_url_prod: https://buy.itunes.apple.com/verifyReceipt
  apple_verify_url_sandbox: https://sandbox.itunes.apple.com/verifyReceipt
EOF

cat >"$VALID_TAURI" <<'EOF'
iap:
  purchase_mode: native
  allowed_product_ids:
    - com.echoisle.coins.60
    - com.echoisle.coins.120
  native_bridge:
    bin: /usr/local/bin/iap-storekit-bridge
    args: []
EOF

cat >"$VALID_AI_ENV" <<'EOF'
AI_JUDGE_PROVIDER=openai
AI_JUDGE_OPENAI_FALLBACK_TO_MOCK=false
OPENAI_API_KEY=sk-test
EOF

cat >"$VALID_V2D_REG" <<'EOF'
REGRESSION_CHAT_TEST_DEBATE_MVP_SIGNOFF=pass
REGRESSION_CHAT_SERVER_NEXTEST=pass
REGRESSION_NOTIFY_SERVER_NEXTEST=pass
REGRESSION_LAST_RUN_AT=2026-03-04T12:00:00Z
EOF

cat >"$VALID_V2D_LOAD" <<'EOF'
LOADTEST_STAGE=preprod
LOAD_SCENARIOS=L1,L2,L3,L4,SOAK,SPIKE
L1_RESULT=pass
L2_RESULT=pass
L3_RESULT=pass
L4_RESULT=pass
SOAK_RESULT=pass
SPIKE_RESULT=pass
REALTIME_MESSAGE_SUCCESS_RATE=99.6
REALTIME_MESSAGE_P95_MS=280
WS_BROADCAST_P95_MS=900
PIN_CHAIN_SUCCESS_RATE=99.92
PIN_CHAIN_P95_MS=430
AI_JUDGE_P95_SECONDS=240
EOF

cat >"$BAD_V2D_REG" <<'EOF'
REGRESSION_CHAT_TEST_DEBATE_MVP_SIGNOFF=fail
REGRESSION_CHAT_SERVER_NEXTEST=pass
REGRESSION_NOTIFY_SERVER_NEXTEST=pass
REGRESSION_LAST_RUN_AT=2026-03-04T12:00:00Z
EOF

cat >"$VALID_M7_REG" <<'EOF'
REGRESSION_AI_JUDGE_M7_ACCEPTANCE=pass
REGRESSION_AI_JUDGE_M7_GATE=pass
REGRESSION_AI_JUDGE_UNITTEST_ALL=pass
REGRESSION_LAST_RUN_AT=2026-03-05T02:20:00Z
EOF

cat >"$VALID_M7_LOAD" <<'EOF'
LOADTEST_STAGE=preprod
LOAD_SCENARIOS=SOAK,SPIKE
SOAK_RESULT=pass
SPIKE_RESULT=pass
AI_JUDGE_SUCCESS_RATE=98.6
AI_JUDGE_P95_SECONDS=240
EOF

cat >"$VALID_M7_FAULT" <<'EOF'
FAULT_SCENARIOS=provider_timeout,provider_overload,rag_unavailable,model_overload,consistency_conflict
FI_PROVIDER_TIMEOUT=pass
FI_PROVIDER_OVERLOAD=pass
FI_RAG_UNAVAILABLE=pass
FI_MODEL_OVERLOAD=pass
FI_CONSISTENCY_CONFLICT=pass
FI_LAST_RUN_AT=2026-03-05T03:00:00Z
EOF

cat >"$BAD_M7_FAULT" <<'EOF'
FAULT_SCENARIOS=provider_timeout,rag_unavailable
FI_PROVIDER_TIMEOUT=pass
FI_PROVIDER_OVERLOAD=fail
FI_RAG_UNAVAILABLE=pass
FI_MODEL_OVERLOAD=pass
FI_CONSISTENCY_CONFLICT=pass
EOF

cat >"$SUPPLY_GATE_PASS" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
while [[ $# -gt 0 ]]; do
  case "$1" in
    --report-out)
      report_out="$2"
      shift 2
      ;;
    *)
      shift
      ;;
  esac
done
if [[ -n "${report_out:-}" ]]; then
  mkdir -p "$(dirname "$report_out")"
  echo "# mock supply chain report" >"$report_out"
fi
exit 0
EOF
chmod +x "$SUPPLY_GATE_PASS"

cat >"$SUPPLY_GATE_FAIL" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
exit 1
EOF
chmod +x "$SUPPLY_GATE_FAIL"

FRESH_CHAOS_LAST_RUN_AT="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
cat >"$VALID_SUPPLY_CHAOS" <<EOF
CHAOS_STAGE=preprod
CHAOS_SCENARIOS=advisory_source_unavailable,pip_audit_missing,allowlist_expired
SCENARIO_ADVISORY_SOURCE_UNAVAILABLE=pass
SCENARIO_PIP_AUDIT_MISSING=pass
SCENARIO_ALLOWLIST_EXPIRED=pass
CHAOS_LAST_RUN_AT=$FRESH_CHAOS_LAST_RUN_AT
EOF

cat >"$BAD_SUPPLY_CHAOS" <<'EOF'
CHAOS_STAGE=preprod
CHAOS_SCENARIOS=advisory_source_unavailable,pip_audit_missing,allowlist_expired
SCENARIO_ADVISORY_SOURCE_UNAVAILABLE=pass
SCENARIO_PIP_AUDIT_MISSING=fail
SCENARIO_ALLOWLIST_EXPIRED=pass
CHAOS_LAST_RUN_AT=2026-03-08T12:00:00Z
EOF

cat >"$STALE_SUPPLY_CHAOS" <<'EOF'
CHAOS_STAGE=preprod
CHAOS_SCENARIOS=advisory_source_unavailable,pip_audit_missing,allowlist_expired
SCENARIO_ADVISORY_SOURCE_UNAVAILABLE=pass
SCENARIO_PIP_AUDIT_MISSING=pass
SCENARIO_ALLOWLIST_EXPIRED=pass
CHAOS_LAST_RUN_AT=2020-01-01T00:00:00Z
EOF

cat >"$VALID_SBOM_RUST" <<'EOF'
{"generatedAt":"2026-03-08T12:00:00Z","format":"test","targets":[{"target":"chat","components":[{"name":"axum","version":"0.7.0"}]}]}
EOF

cat >"$VALID_SBOM_PYTHON" <<'EOF'
{"generatedAt":"2026-03-08T12:00:00Z","format":"test","components":[{"name":"fastapi","version":"0.116.1","pinned":true}]}
EOF

cat >"$VALID_SBOM_LICENSE" <<'EOF'
LICENSE_GENERATED_AT=2026-03-08T12:00:00Z
LICENSE_CHECK_RUST=pass
LICENSE_CHECK_PYTHON_PINNED=pass
LICENSE_CHECK_PYTHON_METADATA=warn
EOF

FRESH_SBOM_GENERATED_AT="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
SBOM_RUST_SHA="$(compute_sha256 "$VALID_SBOM_RUST")"
SBOM_PYTHON_SHA="$(compute_sha256 "$VALID_SBOM_PYTHON")"
SBOM_LICENSE_SHA="$(compute_sha256 "$VALID_SBOM_LICENSE")"

cat >"$VALID_SBOM_EVIDENCE" <<EOF
SBOM_STAGE=preprod
SBOM_GENERATED_AT=$FRESH_SBOM_GENERATED_AT
SBOM_RUST_PATH=$VALID_SBOM_RUST
SBOM_PYTHON_PATH=$VALID_SBOM_PYTHON
SBOM_LICENSE_ATTESTATION_PATH=$VALID_SBOM_LICENSE
SBOM_RUST_SHA256=$SBOM_RUST_SHA
SBOM_PYTHON_SHA256=$SBOM_PYTHON_SHA
SBOM_LICENSE_SHA256=$SBOM_LICENSE_SHA
SBOM_LICENSE_CHECK_RUST=pass
SBOM_LICENSE_CHECK_PYTHON_PINNED=pass
EOF

cat >"$BAD_SBOM_EVIDENCE_HASH" <<EOF
SBOM_STAGE=preprod
SBOM_GENERATED_AT=$FRESH_SBOM_GENERATED_AT
SBOM_RUST_PATH=$VALID_SBOM_RUST
SBOM_PYTHON_PATH=$VALID_SBOM_PYTHON
SBOM_LICENSE_ATTESTATION_PATH=$VALID_SBOM_LICENSE
SBOM_RUST_SHA256=deadbeef
SBOM_PYTHON_SHA256=$SBOM_PYTHON_SHA
SBOM_LICENSE_SHA256=$SBOM_LICENSE_SHA
SBOM_LICENSE_CHECK_RUST=pass
SBOM_LICENSE_CHECK_PYTHON_PINNED=pass
EOF

cat >"$STALE_SBOM_EVIDENCE" <<EOF
SBOM_STAGE=preprod
SBOM_GENERATED_AT=2020-01-01T00:00:00Z
SBOM_RUST_PATH=$VALID_SBOM_RUST
SBOM_PYTHON_PATH=$VALID_SBOM_PYTHON
SBOM_LICENSE_ATTESTATION_PATH=$VALID_SBOM_LICENSE
SBOM_RUST_SHA256=$SBOM_RUST_SHA
SBOM_PYTHON_SHA256=$SBOM_PYTHON_SHA
SBOM_LICENSE_SHA256=$SBOM_LICENSE_SHA
SBOM_LICENSE_CHECK_RUST=pass
SBOM_LICENSE_CHECK_PYTHON_PINNED=pass
EOF

expect_pass "valid production config should pass" \
  "$SCRIPT" \
  --runtime-env production \
  --chat-config "$VALID_CHAT" \
  --tauri-app-config "$VALID_TAURI" \
  --ai-judge-env "$VALID_AI_ENV"

expect_pass "valid production config with v2d gate should pass" \
  "$SCRIPT" \
  --runtime-env production \
  --chat-config "$VALID_CHAT" \
  --tauri-app-config "$VALID_TAURI" \
  --ai-judge-env "$VALID_AI_ENV" \
  --enforce-v2d-stage-acceptance \
  --v2d-regression-evidence "$VALID_V2D_REG" \
  --v2d-load-summary "$VALID_V2D_LOAD" \
  --v2d-report-out "$TMP_DIR/v2d.report.pass.md"

expect_fail "v2d gate fail should fail preflight" \
  "$SCRIPT" \
  --runtime-env production \
  --chat-config "$VALID_CHAT" \
  --tauri-app-config "$VALID_TAURI" \
  --ai-judge-env "$VALID_AI_ENV" \
  --enforce-v2d-stage-acceptance \
  --v2d-regression-evidence "$BAD_V2D_REG" \
  --v2d-load-summary "$VALID_V2D_LOAD" \
  --v2d-report-out "$TMP_DIR/v2d.report.fail.md"

expect_pass "valid production config with ai judge m7 gate should pass" \
  "$SCRIPT" \
  --runtime-env production \
  --chat-config "$VALID_CHAT" \
  --tauri-app-config "$VALID_TAURI" \
  --ai-judge-env "$VALID_AI_ENV" \
  --enforce-ai-judge-m7-acceptance \
  --ai-judge-m7-regression-evidence "$VALID_M7_REG" \
  --ai-judge-m7-preprod-summary "$VALID_M7_LOAD" \
  --ai-judge-m7-fault-matrix "$VALID_M7_FAULT" \
  --ai-judge-m7-report-out "$TMP_DIR/m7.report.pass.md"

expect_fail "ai judge m7 gate fail should fail preflight" \
  "$SCRIPT" \
  --runtime-env production \
  --chat-config "$VALID_CHAT" \
  --tauri-app-config "$VALID_TAURI" \
  --ai-judge-env "$VALID_AI_ENV" \
  --enforce-ai-judge-m7-acceptance \
  --ai-judge-m7-regression-evidence "$VALID_M7_REG" \
  --ai-judge-m7-preprod-summary "$VALID_M7_LOAD" \
  --ai-judge-m7-fault-matrix "$BAD_M7_FAULT" \
  --ai-judge-m7-report-out "$TMP_DIR/m7.report.fail.md"

expect_pass "valid production config with supply chain gate should pass" \
  "$SCRIPT" \
  --runtime-env production \
  --chat-config "$VALID_CHAT" \
  --tauri-app-config "$VALID_TAURI" \
  --ai-judge-env "$VALID_AI_ENV" \
  --enforce-supply-chain-security \
  --supply-chain-gate-script "$SUPPLY_GATE_PASS" \
  --supply-chain-report-out "$TMP_DIR/supply.report.pass.md"

expect_fail "supply chain gate fail should fail preflight" \
  "$SCRIPT" \
  --runtime-env production \
  --chat-config "$VALID_CHAT" \
  --tauri-app-config "$VALID_TAURI" \
  --ai-judge-env "$VALID_AI_ENV" \
  --enforce-supply-chain-security \
  --supply-chain-gate-script "$SUPPLY_GATE_FAIL" \
  --supply-chain-report-out "$TMP_DIR/supply.report.fail.md"

expect_pass "fresh supply chain chaos evidence should pass preflight" \
  "$SCRIPT" \
  --runtime-env production \
  --chat-config "$VALID_CHAT" \
  --tauri-app-config "$VALID_TAURI" \
  --ai-judge-env "$VALID_AI_ENV" \
  --enforce-supply-chain-chaos-evidence \
  --supply-chain-chaos-evidence "$VALID_SUPPLY_CHAOS" \
  --supply-chain-chaos-max-age-hours 24

expect_fail "chaos evidence with failed scenario should fail preflight" \
  "$SCRIPT" \
  --runtime-env production \
  --chat-config "$VALID_CHAT" \
  --tauri-app-config "$VALID_TAURI" \
  --ai-judge-env "$VALID_AI_ENV" \
  --enforce-supply-chain-chaos-evidence \
  --supply-chain-chaos-evidence "$BAD_SUPPLY_CHAOS" \
  --supply-chain-chaos-max-age-hours 24

expect_fail "stale chaos evidence should fail preflight" \
  "$SCRIPT" \
  --runtime-env production \
  --chat-config "$VALID_CHAT" \
  --tauri-app-config "$VALID_TAURI" \
  --ai-judge-env "$VALID_AI_ENV" \
  --enforce-supply-chain-chaos-evidence \
  --supply-chain-chaos-evidence "$STALE_SUPPLY_CHAOS" \
  --supply-chain-chaos-max-age-hours 24

expect_pass "fresh supply chain sbom evidence should pass preflight" \
  "$SCRIPT" \
  --runtime-env production \
  --chat-config "$VALID_CHAT" \
  --tauri-app-config "$VALID_TAURI" \
  --ai-judge-env "$VALID_AI_ENV" \
  --enforce-supply-chain-sbom-attestation \
  --supply-chain-sbom-evidence "$VALID_SBOM_EVIDENCE" \
  --supply-chain-sbom-max-age-hours 24

expect_fail "sbom evidence with hash mismatch should fail preflight" \
  "$SCRIPT" \
  --runtime-env production \
  --chat-config "$VALID_CHAT" \
  --tauri-app-config "$VALID_TAURI" \
  --ai-judge-env "$VALID_AI_ENV" \
  --enforce-supply-chain-sbom-attestation \
  --supply-chain-sbom-evidence "$BAD_SBOM_EVIDENCE_HASH" \
  --supply-chain-sbom-max-age-hours 24

expect_fail "stale sbom evidence should fail preflight" \
  "$SCRIPT" \
  --runtime-env production \
  --chat-config "$VALID_CHAT" \
  --tauri-app-config "$VALID_TAURI" \
  --ai-judge-env "$VALID_AI_ENV" \
  --enforce-supply-chain-sbom-attestation \
  --supply-chain-sbom-evidence "$STALE_SBOM_EVIDENCE" \
  --supply-chain-sbom-max-age-hours 24

BAD_CHAT_MOCK="$TMP_DIR/chat.mock.yml"
cat >"$BAD_CHAT_MOCK" <<'EOF'
payment:
  verify_mode: mock
  apple_verify_url_prod: https://buy.itunes.apple.com/verifyReceipt
  apple_verify_url_sandbox: https://sandbox.itunes.apple.com/verifyReceipt
EOF

expect_fail "payment mock in production should fail" \
  "$SCRIPT" \
  --runtime-env production \
  --chat-config "$BAD_CHAT_MOCK" \
  --tauri-app-config "$VALID_TAURI" \
  --ai-judge-env "$VALID_AI_ENV"

BAD_TAURI_SIMULATE="$TMP_DIR/app.simulate.yml"
cat >"$BAD_TAURI_SIMULATE" <<'EOF'
iap:
  purchase_mode: native
  allowed_product_ids:
    - com.echoisle.coins.60
  native_bridge:
    bin: /usr/local/bin/iap-storekit-bridge
    args:
      - --simulate
EOF

expect_fail "tauri simulate arg in production should fail" \
  "$SCRIPT" \
  --runtime-env production \
  --chat-config "$VALID_CHAT" \
  --tauri-app-config "$BAD_TAURI_SIMULATE" \
  --ai-judge-env "$VALID_AI_ENV"

BAD_AI_MOCK="$TMP_DIR/ai.mock.env"
cat >"$BAD_AI_MOCK" <<'EOF'
AI_JUDGE_PROVIDER=mock
AI_JUDGE_OPENAI_FALLBACK_TO_MOCK=false
OPENAI_API_KEY=
EOF

expect_fail "ai_judge provider mock in production should fail" \
  "$SCRIPT" \
  --runtime-env production \
  --chat-config "$VALID_CHAT" \
  --tauri-app-config "$VALID_TAURI" \
  --ai-judge-env "$BAD_AI_MOCK"

echo "all preflight tests passed"
