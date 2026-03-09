#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage:
  supply_chain_preprod_chaos_drill.sh [options]

Options:
  --root <path>                   Repo root path (default: git top-level or cwd)
  --report-out <path>             Markdown report output path
                                  default: docs/dev_plan/供应链预发故障注入演练报告-<YYYY-MM-DD>.md
  --evidence-out <path>           Chaos drill evidence env output path
                                  default: docs/loadtest/evidence/supply_chain_preprod_chaos.env
  --supply-chain-gate-script <path>
                                  default: scripts/release/supply_chain_security_gate.sh
  --python-requirements <path>    default: ai_judge_service/requirements.txt
  --cargo-advisory-allowlist <path>
                                  default: scripts/release/security_allowlists/cargo_deny_advisories_allowlist.csv
  --pip-audit-allowlist <path>
                                  default: scripts/release/security_allowlists/pip_audit_vulns_allowlist.csv
  -h, --help                      Show this help

Scenarios:
  1) advisory_source_unavailable
  2) pip_audit_missing
  3) allowlist_expired
USAGE
}

trim() {
  local value="$1"
  value="${value#${value%%[![:space:]]*}}"
  value="${value%${value##*[![:space:]]}}"
  printf '%s' "$value"
}

PASS_ITEMS=()
FAIL_ITEMS=()
WARN_ITEMS=()
PASS_COUNT=0
FAIL_COUNT=0
WARN_COUNT=0

mark_pass() {
  PASS_ITEMS+=("$1")
  PASS_COUNT=$((PASS_COUNT + 1))
}

mark_fail() {
  FAIL_ITEMS+=("$1")
  FAIL_COUNT=$((FAIL_COUNT + 1))
}

mark_warn() {
  WARN_ITEMS+=("$1")
  WARN_COUNT=$((WARN_COUNT + 1))
}

ROOT=""
REPORT_OUT=""
EVIDENCE_OUT=""
SUPPLY_CHAIN_GATE_SCRIPT=""
PYTHON_REQUIREMENTS=""
CARGO_ADVISORY_ALLOWLIST=""
PIP_AUDIT_ALLOWLIST=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --root)
      ROOT="$2"
      shift 2
      ;;
    --report-out)
      REPORT_OUT="$2"
      shift 2
      ;;
    --evidence-out)
      EVIDENCE_OUT="$2"
      shift 2
      ;;
    --supply-chain-gate-script)
      SUPPLY_CHAIN_GATE_SCRIPT="$2"
      shift 2
      ;;
    --python-requirements)
      PYTHON_REQUIREMENTS="$2"
      shift 2
      ;;
    --cargo-advisory-allowlist)
      CARGO_ADVISORY_ALLOWLIST="$2"
      shift 2
      ;;
    --pip-audit-allowlist)
      PIP_AUDIT_ALLOWLIST="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage
      exit 1
      ;;
  esac
done

if [[ -z "$ROOT" ]]; then
  if git rev-parse --show-toplevel >/dev/null 2>&1; then
    ROOT="$(git rev-parse --show-toplevel)"
  else
    ROOT="$(pwd)"
  fi
fi

if [[ -z "$SUPPLY_CHAIN_GATE_SCRIPT" ]]; then
  SUPPLY_CHAIN_GATE_SCRIPT="$ROOT/scripts/release/supply_chain_security_gate.sh"
fi
if [[ -z "$REPORT_OUT" ]]; then
  REPORT_OUT="$ROOT/docs/dev_plan/供应链预发故障注入演练报告-$(date +%F).md"
fi
if [[ -z "$EVIDENCE_OUT" ]]; then
  EVIDENCE_OUT="$ROOT/docs/loadtest/evidence/supply_chain_preprod_chaos.env"
fi
if [[ -z "$PYTHON_REQUIREMENTS" ]]; then
  PYTHON_REQUIREMENTS="$ROOT/ai_judge_service/requirements.txt"
fi
if [[ -z "$CARGO_ADVISORY_ALLOWLIST" ]]; then
  CARGO_ADVISORY_ALLOWLIST="$ROOT/scripts/release/security_allowlists/cargo_deny_advisories_allowlist.csv"
fi
if [[ -z "$PIP_AUDIT_ALLOWLIST" ]]; then
  PIP_AUDIT_ALLOWLIST="$ROOT/scripts/release/security_allowlists/pip_audit_vulns_allowlist.csv"
fi

mkdir -p "$(dirname "$REPORT_OUT")"
mkdir -p "$(dirname "$EVIDENCE_OUT")"

if [[ ! -x "$SUPPLY_CHAIN_GATE_SCRIPT" ]]; then
  if [[ -f "$SUPPLY_CHAIN_GATE_SCRIPT" ]]; then
    chmod +x "$SUPPLY_CHAIN_GATE_SCRIPT"
  else
    echo "supply chain gate script not found: $SUPPLY_CHAIN_GATE_SCRIPT" >&2
    exit 1
  fi
fi

if [[ ! -f "$PYTHON_REQUIREMENTS" ]]; then
  echo "python requirements not found: $PYTHON_REQUIREMENTS" >&2
  exit 1
fi
if [[ ! -f "$CARGO_ADVISORY_ALLOWLIST" ]]; then
  echo "cargo advisory allowlist not found: $CARGO_ADVISORY_ALLOWLIST" >&2
  exit 1
fi
if [[ ! -f "$PIP_AUDIT_ALLOWLIST" ]]; then
  echo "pip audit allowlist not found: $PIP_AUDIT_ALLOWLIST" >&2
  exit 1
fi

echo "== Supply chain preprod chaos drill =="
echo "root: $ROOT"
echo "supply_chain_gate_script: $SUPPLY_CHAIN_GATE_SCRIPT"
echo "python_requirements: $PYTHON_REQUIREMENTS"
echo "report_out: $REPORT_OUT"
echo "evidence_out: $EVIDENCE_OUT"
echo

TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

BIN_DIR="$TMP_DIR/bin"
mkdir -p "$BIN_DIR"

cat >"$BIN_DIR/cargo-audit-network-fail" <<'EOF_AUDIT_FAIL'
#!/usr/bin/env bash
set -euo pipefail
echo "failed to fetch advisory database: simulated network outage" >&2
exit 1
EOF_AUDIT_FAIL
chmod +x "$BIN_DIR/cargo-audit-network-fail"

cat >"$BIN_DIR/cargo-audit-pass" <<'EOF_AUDIT_PASS'
#!/usr/bin/env bash
set -euo pipefail
exit 0
EOF_AUDIT_PASS
chmod +x "$BIN_DIR/cargo-audit-pass"

cat >"$BIN_DIR/cargo-deny-pass" <<'EOF_DENY_PASS'
#!/usr/bin/env bash
set -euo pipefail
exit 0
EOF_DENY_PASS
chmod +x "$BIN_DIR/cargo-deny-pass"

cat >"$BIN_DIR/python-pip-audit-pass" <<'EOF_PY_PASS'
#!/usr/bin/env bash
set -euo pipefail
if [[ "$#" -ge 2 && "$1" == "-m" && "$2" == "pip_audit" ]]; then
  exit 0
fi
exit 2
EOF_PY_PASS
chmod +x "$BIN_DIR/python-pip-audit-pass"

cat >"$BIN_DIR/python-pip-audit-missing" <<'EOF_PY_MISSING'
#!/usr/bin/env bash
set -euo pipefail
if [[ "$#" -ge 2 && "$1" == "-m" && "$2" == "pip_audit" ]]; then
  echo "No module named pip_audit" >&2
  exit 1
fi
exit 2
EOF_PY_MISSING
chmod +x "$BIN_DIR/python-pip-audit-missing"

EXPIRED_CARGO_ALLOWLIST="$TMP_DIR/cargo_expired.csv"
cat >"$EXPIRED_CARGO_ALLOWLIST" <<'EOF_EXPIRED_CARGO'
# advisory_id,target,expires_on,owner,reason
RUSTSEC-2099-0001,chat,2020-01-01,preprod-chaos-drill,simulate expired waiver
EOF_EXPIRED_CARGO

scenario_advisory_source_unavailable="fail"
scenario_pip_audit_missing="fail"
scenario_allowlist_expired="fail"

run_expect_block() {
  local scenario_name="$1"
  shift
  if "$@" >/dev/null 2>&1; then
    mark_fail "$scenario_name: gate unexpectedly passed"
    return 1
  fi
  mark_pass "$scenario_name: gate blocked as expected"
  return 0
}

SC1_REPORT="$TMP_DIR/scenario_advisory_source_unavailable.md"
if run_expect_block "advisory_source_unavailable" \
  env CHAOS_SCENARIO="advisory_source_unavailable" \
  bash "$SUPPLY_CHAIN_GATE_SCRIPT" \
    --root "$ROOT" \
    --report-out "$SC1_REPORT" \
    --cargo-audit-bin "$BIN_DIR/cargo-audit-network-fail" \
    --cargo-deny-bin "$BIN_DIR/cargo-deny-pass" \
    --python-bin "$BIN_DIR/python-pip-audit-pass" \
    --python-requirements "$PYTHON_REQUIREMENTS" \
    --cargo-advisory-allowlist "$CARGO_ADVISORY_ALLOWLIST" \
    --pip-audit-allowlist "$PIP_AUDIT_ALLOWLIST"; then
  scenario_advisory_source_unavailable="pass"
fi

SC2_REPORT="$TMP_DIR/scenario_pip_audit_missing.md"
if run_expect_block "pip_audit_missing" \
  env CHAOS_SCENARIO="pip_audit_missing" \
  bash "$SUPPLY_CHAIN_GATE_SCRIPT" \
    --root "$ROOT" \
    --report-out "$SC2_REPORT" \
    --cargo-audit-bin "$BIN_DIR/cargo-audit-pass" \
    --cargo-deny-bin "$BIN_DIR/cargo-deny-pass" \
    --python-bin "$BIN_DIR/python-pip-audit-missing" \
    --python-requirements "$PYTHON_REQUIREMENTS" \
    --cargo-advisory-allowlist "$CARGO_ADVISORY_ALLOWLIST" \
    --pip-audit-allowlist "$PIP_AUDIT_ALLOWLIST"; then
  scenario_pip_audit_missing="pass"
fi

SC3_REPORT="$TMP_DIR/scenario_allowlist_expired.md"
if run_expect_block "allowlist_expired" \
  env CHAOS_SCENARIO="allowlist_expired" \
  bash "$SUPPLY_CHAIN_GATE_SCRIPT" \
    --root "$ROOT" \
    --report-out "$SC3_REPORT" \
    --cargo-audit-bin "$BIN_DIR/cargo-audit-pass" \
    --cargo-deny-bin "$BIN_DIR/cargo-deny-pass" \
    --python-bin "$BIN_DIR/python-pip-audit-pass" \
    --python-requirements "$PYTHON_REQUIREMENTS" \
    --cargo-advisory-allowlist "$EXPIRED_CARGO_ALLOWLIST" \
    --pip-audit-allowlist "$PIP_AUDIT_ALLOWLIST"; then
  scenario_allowlist_expired="pass"
fi

CHAOS_LAST_RUN_AT="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
{
  echo "CHAOS_STAGE=preprod"
  echo "CHAOS_SCENARIOS=advisory_source_unavailable,pip_audit_missing,allowlist_expired"
  echo "SCENARIO_ADVISORY_SOURCE_UNAVAILABLE=$scenario_advisory_source_unavailable"
  echo "SCENARIO_PIP_AUDIT_MISSING=$scenario_pip_audit_missing"
  echo "SCENARIO_ALLOWLIST_EXPIRED=$scenario_allowlist_expired"
  echo "CHAOS_LAST_RUN_AT=$CHAOS_LAST_RUN_AT"
  echo "CHAOS_REPORT_OUT=$REPORT_OUT"
} >"$EVIDENCE_OUT"

{
  echo "# 供应链预发故障注入演练报告"
  echo
  echo "- 生成时间: $(date '+%Y-%m-%d %H:%M:%S %z')"
  echo "- root: $ROOT"
  echo "- supply_chain_gate_script: $SUPPLY_CHAIN_GATE_SCRIPT"
  echo "- evidence_out: $EVIDENCE_OUT"
  echo
  echo "## 场景结果"
  echo "- advisory_source_unavailable: $scenario_advisory_source_unavailable"
  echo "- pip_audit_missing: $scenario_pip_audit_missing"
  echo "- allowlist_expired: $scenario_allowlist_expired"
  echo
  echo "## 通过项 ($PASS_COUNT)"
  if [[ "$PASS_COUNT" -eq 0 ]]; then
    echo "- (none)"
  else
    for item in "${PASS_ITEMS[@]-}"; do
      [[ -z "$item" ]] && continue
      echo "- $item"
    done
  fi
  echo
  echo "## 预警项 ($WARN_COUNT)"
  if [[ "$WARN_COUNT" -eq 0 ]]; then
    echo "- (none)"
  else
    for item in "${WARN_ITEMS[@]-}"; do
      [[ -z "$item" ]] && continue
      echo "- $item"
    done
  fi
  echo
  echo "## 失败项 ($FAIL_COUNT)"
  if [[ "$FAIL_COUNT" -eq 0 ]]; then
    echo "- (none)"
  else
    for item in "${FAIL_ITEMS[@]-}"; do
      [[ -z "$item" ]] && continue
      echo "- $item"
    done
  fi
  echo
  echo "## 场景日志路径"
  echo "- advisory_source_unavailable: $SC1_REPORT"
  echo "- pip_audit_missing: $SC2_REPORT"
  echo "- allowlist_expired: $SC3_REPORT"
} >"$REPORT_OUT"

echo "---- PASS ----"
for item in "${PASS_ITEMS[@]-}"; do
  [[ -z "$item" ]] && continue
  echo "[PASS] $item"
done
[[ "$PASS_COUNT" -eq 0 ]] && echo "(none)"

echo
echo "---- WARN ----"
for item in "${WARN_ITEMS[@]-}"; do
  [[ -z "$item" ]] && continue
  echo "[WARN] $item"
done
[[ "$WARN_COUNT" -eq 0 ]] && echo "(none)"

echo
echo "---- FAIL ----"
for item in "${FAIL_ITEMS[@]-}"; do
  [[ -z "$item" ]] && continue
  echo "[FAIL] $item"
done
[[ "$FAIL_COUNT" -eq 0 ]] && echo "(none)"

echo
if [[ "$FAIL_COUNT" -gt 0 ]]; then
  echo "chaos drill result: FAILED ($FAIL_COUNT issue(s))"
  exit 1
fi
echo "chaos drill result: PASSED"
