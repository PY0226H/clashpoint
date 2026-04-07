#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage:
  appstore_preflight_check.sh [options]

Options:
  --runtime-env <env>          Runtime env label, default: production
  --chat-config <path>         chat_server config yaml, default: chat/chat_server/chat.yml
  --tauri-app-config <path>    Tauri app.yml path for IAP native bridge checks
  --ai-judge-env <path>        AI judge env file (KEY=VALUE)
  --enforce-v2d-stage-acceptance
                               Enable V2-D stage acceptance gate check
  --v2d-regression-evidence <path>
                               V2-D regression evidence env file
  --v2d-load-summary <path>    V2-D preprod load summary env file
  --v2d-report-out <path>      V2-D acceptance report output path
  --v2d-allow-missing-scenarios
                               Pass through --allow-missing-scenarios to V2-D gate
  --enforce-ai-judge-m7-acceptance
                               Enable AI Judge M7 stage acceptance gate check
  --ai-judge-m7-regression-evidence <path>
                               AI Judge M7 regression evidence env file
  --ai-judge-m7-preprod-summary <path>
                               AI Judge M7 preprod summary env file
  --ai-judge-m7-fault-matrix <path>
                               AI Judge M7 fault matrix env file
  --ai-judge-m7-report-out <path>
                               AI Judge M7 acceptance report output path
  --ai-judge-m7-allow-missing-scenarios
                               Pass through --allow-missing-scenarios to AI Judge M7 gate
  --enforce-supply-chain-security
                               Enable supply chain security gate check
  --supply-chain-report-out <path>
                               Supply chain gate report output path
  --supply-chain-allow-missing-tools
                               Pass through --allow-missing-tools to supply chain gate
  --supply-chain-gate-script <path>
                               Override supply chain gate script path (test/debug)
  --supply-chain-cargo-allowlist <path>
                               Override cargo advisory allowlist CSV for supply chain gate
  --supply-chain-pip-allowlist <path>
                               Override pip-audit allowlist CSV for supply chain gate
  --enforce-supply-chain-chaos-evidence
                               Enable supply chain chaos evidence freshness gate check
  --supply-chain-chaos-evidence <path>
                               Supply chain chaos evidence env file
  --supply-chain-chaos-max-age-hours <hours>
                               Max age in hours for chaos evidence, default: 168
  --enforce-supply-chain-sbom-attestation
                               Enable supply chain SBOM and license attestation gate check
  --supply-chain-sbom-evidence <path>
                               Supply chain SBOM attestation evidence env file
  --supply-chain-sbom-max-age-hours <hours>
                               Max age in hours for SBOM attestation evidence, default: 168
  --root <path>                Repo root path (default: git top-level or cwd)
  -h, --help                   Show this help

Notes:
  1) Production checks are enabled when runtime env is prod|production.
  2) AI judge values are read from --ai-judge-env first, then process env.
  3) Tauri checks are skipped when --tauri-app-config is not provided.
  4) V2-D gate is optional and runs only when --enforce-v2d-stage-acceptance is set.
  5) AI Judge M7 gate is optional and runs only when --enforce-ai-judge-m7-acceptance is set.
  6) Supply chain gate is optional and runs only when --enforce-supply-chain-security is set.
  7) Supply chain chaos evidence gate is optional and runs only when --enforce-supply-chain-chaos-evidence is set.
  8) Supply chain SBOM attestation gate is optional and runs only when --enforce-supply-chain-sbom-attestation is set.
USAGE
}

trim() {
  local value="$1"
  value="${value#${value%%[![:space:]]*}}"
  value="${value%${value##*[![:space:]]}}"
  printf '%s' "$value"
}

strip_quotes() {
  local value
  value="$(trim "$1")"
  if [[ "$value" =~ ^\".*\"$ ]]; then
    value="${value:1:${#value}-2}"
  elif [[ "$value" =~ ^\'.*\'$ ]]; then
    value="${value:1:${#value}-2}"
  fi
  printf '%s' "$value"
}

to_lower() {
  printf '%s' "$1" | tr '[:upper:]' '[:lower:]'
}

is_production_env() {
  local value
  value="$(to_lower "$(trim "$1")")"
  [[ "$value" == "prod" || "$value" == "production" ]]
}

normalize_provider() {
  local value
  value="$(to_lower "$(trim "$1")")"
  if [[ "$value" == "mock" || "$value" == "dev_mock" ]]; then
    printf 'mock'
    return
  fi
  printf 'openai'
}

normalize_payment_mode() {
  local value
  value="$(to_lower "$(trim "$1")")"
  if [[ "$value" == "mock" || "$value" == "dev_mock" ]]; then
    printf 'mock'
    return
  fi
  printf 'apple'
}

normalize_iap_purchase_mode() {
  local value
  value="$(to_lower "$(trim "$1")")"
  if [[ "$value" == "mock" || "$value" == "dev_mock" ]]; then
    printf 'mock'
    return
  fi
  printf 'native'
}

normalize_bool() {
  local value
  value="$(to_lower "$(trim "$1")")"
  if [[ "$value" == "1" || "$value" == "true" || "$value" == "yes" || "$value" == "on" ]]; then
    printf 'true'
    return
  fi
  printf 'false'
}

parse_epoch_from_iso8601_utc() {
  local value
  value="$(trim "$1")"
  if [[ -z "$value" ]]; then
    return 1
  fi

  if date -u -d "$value" +%s >/dev/null 2>&1; then
    date -u -d "$value" +%s
    return 0
  fi

  if date -u -j -f "%Y-%m-%dT%H:%M:%SZ" "$value" +%s >/dev/null 2>&1; then
    date -u -j -f "%Y-%m-%dT%H:%M:%SZ" "$value" +%s
    return 0
  fi

  return 1
}

sha256_file() {
  local file="$1"
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum "$file" | awk '{print $1}'
    return 0
  fi
  if command -v shasum >/dev/null 2>&1; then
    shasum -a 256 "$file" | awk '{print $1}'
    return 0
  fi
  return 1
}

read_yaml_scalar_in_section() {
  local file="$1"
  local section="$2"
  local key="$3"
  awk -v section="$section" -v key="$key" '
    BEGIN { in_section = 0 }
    {
      if ($0 ~ ("^[[:space:]]*" section ":[[:space:]]*$")) {
        in_section = 1
        next
      }
      if (in_section && $0 ~ "^[^[:space:]]") {
        in_section = 0
      }
      if (in_section && $0 ~ ("^[[:space:]]*" key ":[[:space:]]*")) {
        line = $0
        sub("^[[:space:]]*" key ":[[:space:]]*", "", line)
        print line
        exit
      }
    }
  ' "$file"
}

read_yaml_scalar_nested() {
  local file="$1"
  local section="$2"
  local subsection="$3"
  local key="$4"
  awk -v section="$section" -v subsection="$subsection" -v key="$key" '
    BEGIN { in_section = 0; in_subsection = 0 }
    {
      if ($0 ~ ("^[[:space:]]*" section ":[[:space:]]*$")) {
        in_section = 1
        in_subsection = 0
        next
      }
      if (in_section && $0 ~ "^[^[:space:]]") {
        in_section = 0
        in_subsection = 0
      }
      if (in_section && $0 ~ ("^[[:space:]]{2}" subsection ":[[:space:]]*$")) {
        in_subsection = 1
        next
      }
      if (in_section && in_subsection && $0 ~ "^[[:space:]]{2}[a-zA-Z0-9_]+:[[:space:]]*") {
        in_subsection = 0
      }
      if (in_section && in_subsection && $0 ~ ("^[[:space:]]{4}" key ":[[:space:]]*")) {
        line = $0
        sub("^[[:space:]]{4}" key ":[[:space:]]*", "", line)
        print line
        exit
      }
    }
  ' "$file"
}

read_yaml_list_items() {
  local file="$1"
  local section="$2"
  local key="$3"
  awk -v section="$section" -v key="$key" '
    BEGIN { in_section = 0; in_list = 0 }
    {
      if ($0 ~ ("^[[:space:]]*" section ":[[:space:]]*$")) {
        in_section = 1
        in_list = 0
        next
      }
      if (in_section && $0 ~ "^[^[:space:]]") {
        in_section = 0
        in_list = 0
      }
      if (in_section && $0 ~ ("^[[:space:]]{2}" key ":[[:space:]]*")) {
        inline = $0
        sub("^[[:space:]]{2}" key ":[[:space:]]*", "", inline)
        gsub(/^[[:space:]]+|[[:space:]]+$/, "", inline)
        if (inline ~ /^\[.*\]$/) {
          inline = substr(inline, 2, length(inline) - 2)
          n = split(inline, arr, ",")
          for (i = 1; i <= n; i++) {
            item = arr[i]
            gsub(/^[[:space:]]+|[[:space:]]+$/, "", item)
            gsub(/^"|"$/, "", item)
            gsub(/^'\''|'\''$/, "", item)
            if (item != "") {
              print item
            }
          }
          exit
        }
        in_list = 1
        next
      }
      if (in_section && in_list && $0 ~ "^[[:space:]]{2}[a-zA-Z0-9_]+:[[:space:]]*") {
        in_list = 0
      }
      if (in_section && in_list && $0 ~ "^[[:space:]]{4}-[[:space:]]*") {
        item = $0
        sub("^[[:space:]]{4}-[[:space:]]*", "", item)
        gsub(/^[[:space:]]+|[[:space:]]+$/, "", item)
        gsub(/^"|"$/, "", item)
        gsub(/^'\''|'\''$/, "", item)
        if (item != "") {
          print item
        }
      }
    }
  ' "$file"
}

read_yaml_list_items_nested() {
  local file="$1"
  local section="$2"
  local subsection="$3"
  local key="$4"
  awk -v section="$section" -v subsection="$subsection" -v key="$key" '
    BEGIN { in_section = 0; in_subsection = 0; in_list = 0 }
    {
      if ($0 ~ ("^[[:space:]]*" section ":[[:space:]]*$")) {
        in_section = 1
        in_subsection = 0
        in_list = 0
        next
      }
      if (in_section && $0 ~ "^[^[:space:]]") {
        in_section = 0
        in_subsection = 0
        in_list = 0
      }
      if (in_section && $0 ~ ("^[[:space:]]{2}" subsection ":[[:space:]]*$")) {
        in_subsection = 1
        in_list = 0
        next
      }
      if (in_section && in_subsection && $0 ~ "^[[:space:]]{2}[a-zA-Z0-9_]+:[[:space:]]*") {
        in_subsection = 0
        in_list = 0
      }
      if (in_section && in_subsection && $0 ~ ("^[[:space:]]{4}" key ":[[:space:]]*")) {
        inline = $0
        sub("^[[:space:]]{4}" key ":[[:space:]]*", "", inline)
        gsub(/^[[:space:]]+|[[:space:]]+$/, "", inline)
        if (inline ~ /^\[.*\]$/) {
          inline = substr(inline, 2, length(inline) - 2)
          n = split(inline, arr, ",")
          for (i = 1; i <= n; i++) {
            item = arr[i]
            gsub(/^[[:space:]]+|[[:space:]]+$/, "", item)
            gsub(/^"|"$/, "", item)
            gsub(/^'\''|'\''$/, "", item)
            if (item != "") {
              print item
            }
          }
          exit
        }
        in_list = 1
        next
      }
      if (in_section && in_subsection && in_list && $0 ~ "^[[:space:]]{4}[a-zA-Z0-9_]+:[[:space:]]*") {
        in_list = 0
      }
      if (in_section && in_subsection && in_list && $0 ~ "^[[:space:]]{6}-[[:space:]]*") {
        item = $0
        sub("^[[:space:]]{6}-[[:space:]]*", "", item)
        gsub(/^[[:space:]]+|[[:space:]]+$/, "", item)
        gsub(/^"|"$/, "", item)
        gsub(/^'\''|'\''$/, "", item)
        if (item != "") {
          print item
        }
      }
    }
  ' "$file"
}

read_env_value() {
  local key="$1"
  local env_file="${2:-}"
  if [[ -n "$env_file" && -f "$env_file" ]]; then
    local from_file
    from_file="$(
      awk -v key="$key" '
        /^[[:space:]]*#/ { next }
        /^[[:space:]]*$/ { next }
        {
          line = $0
          sub(/^[[:space:]]+/, "", line)
          if (index(line, key "=") == 1) {
            value = substr(line, length(key) + 2)
            sub(/[[:space:]]+#.*/, "", value)
            gsub(/^[[:space:]]+|[[:space:]]+$/, "", value)
            if (value ~ /^".*"$/ || value ~ /^'\''.*'\''$/) {
              value = substr(value, 2, length(value) - 2)
            }
            print value
            exit
          }
        }
      ' "$env_file"
    )"
    if [[ -n "$from_file" ]]; then
      printf '%s' "$from_file"
      return
    fi
  fi

  printf '%s' "${!key-}"
}

PASS_ITEMS=()
FAIL_ITEMS=()
WARN_ITEMS=()
iap_allowed_products=()
iap_args=()
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
RUNTIME_ENV="production"
CHAT_CONFIG=""
TAURI_APP_CONFIG=""
AI_JUDGE_ENV=""
ENFORCE_V2D_STAGE_ACCEPTANCE="false"
V2D_REGRESSION_EVIDENCE=""
V2D_LOAD_SUMMARY=""
V2D_REPORT_OUT=""
V2D_ALLOW_MISSING_SCENARIOS="false"
ENFORCE_AI_JUDGE_M7_ACCEPTANCE="false"
AI_JUDGE_M7_REGRESSION_EVIDENCE=""
AI_JUDGE_M7_PREPROD_SUMMARY=""
AI_JUDGE_M7_FAULT_MATRIX=""
AI_JUDGE_M7_REPORT_OUT=""
AI_JUDGE_M7_ALLOW_MISSING_SCENARIOS="false"
ENFORCE_SUPPLY_CHAIN_SECURITY="false"
SUPPLY_CHAIN_REPORT_OUT=""
SUPPLY_CHAIN_ALLOW_MISSING_TOOLS="false"
SUPPLY_CHAIN_GATE_SCRIPT=""
SUPPLY_CHAIN_CARGO_ADVISORY_ALLOWLIST=""
SUPPLY_CHAIN_PIP_AUDIT_ALLOWLIST=""
ENFORCE_SUPPLY_CHAIN_CHAOS_EVIDENCE="false"
SUPPLY_CHAIN_CHAOS_EVIDENCE=""
SUPPLY_CHAIN_CHAOS_MAX_AGE_HOURS="168"
ENFORCE_SUPPLY_CHAIN_SBOM_ATTESTATION="false"
SUPPLY_CHAIN_SBOM_EVIDENCE=""
SUPPLY_CHAIN_SBOM_MAX_AGE_HOURS="168"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --runtime-env)
      RUNTIME_ENV="$2"
      shift 2
      ;;
    --chat-config)
      CHAT_CONFIG="$2"
      shift 2
      ;;
    --tauri-app-config)
      TAURI_APP_CONFIG="$2"
      shift 2
      ;;
    --ai-judge-env)
      AI_JUDGE_ENV="$2"
      shift 2
      ;;
    --enforce-v2d-stage-acceptance)
      ENFORCE_V2D_STAGE_ACCEPTANCE="true"
      shift
      ;;
    --v2d-regression-evidence)
      V2D_REGRESSION_EVIDENCE="$2"
      shift 2
      ;;
    --v2d-load-summary)
      V2D_LOAD_SUMMARY="$2"
      shift 2
      ;;
    --v2d-report-out)
      V2D_REPORT_OUT="$2"
      shift 2
      ;;
    --v2d-allow-missing-scenarios)
      V2D_ALLOW_MISSING_SCENARIOS="true"
      shift
      ;;
    --enforce-ai-judge-m7-acceptance)
      ENFORCE_AI_JUDGE_M7_ACCEPTANCE="true"
      shift
      ;;
    --ai-judge-m7-regression-evidence)
      AI_JUDGE_M7_REGRESSION_EVIDENCE="$2"
      shift 2
      ;;
    --ai-judge-m7-preprod-summary)
      AI_JUDGE_M7_PREPROD_SUMMARY="$2"
      shift 2
      ;;
    --ai-judge-m7-fault-matrix)
      AI_JUDGE_M7_FAULT_MATRIX="$2"
      shift 2
      ;;
    --ai-judge-m7-report-out)
      AI_JUDGE_M7_REPORT_OUT="$2"
      shift 2
      ;;
    --ai-judge-m7-allow-missing-scenarios)
      AI_JUDGE_M7_ALLOW_MISSING_SCENARIOS="true"
      shift
      ;;
    --enforce-supply-chain-security)
      ENFORCE_SUPPLY_CHAIN_SECURITY="true"
      shift
      ;;
    --supply-chain-report-out)
      SUPPLY_CHAIN_REPORT_OUT="$2"
      shift 2
      ;;
    --supply-chain-allow-missing-tools)
      SUPPLY_CHAIN_ALLOW_MISSING_TOOLS="true"
      shift
      ;;
    --supply-chain-gate-script)
      SUPPLY_CHAIN_GATE_SCRIPT="$2"
      shift 2
      ;;
    --supply-chain-cargo-allowlist)
      SUPPLY_CHAIN_CARGO_ADVISORY_ALLOWLIST="$2"
      shift 2
      ;;
    --supply-chain-pip-allowlist)
      SUPPLY_CHAIN_PIP_AUDIT_ALLOWLIST="$2"
      shift 2
      ;;
    --enforce-supply-chain-chaos-evidence)
      ENFORCE_SUPPLY_CHAIN_CHAOS_EVIDENCE="true"
      shift
      ;;
    --supply-chain-chaos-evidence)
      SUPPLY_CHAIN_CHAOS_EVIDENCE="$2"
      shift 2
      ;;
    --supply-chain-chaos-max-age-hours)
      SUPPLY_CHAIN_CHAOS_MAX_AGE_HOURS="$2"
      shift 2
      ;;
    --enforce-supply-chain-sbom-attestation)
      ENFORCE_SUPPLY_CHAIN_SBOM_ATTESTATION="true"
      shift
      ;;
    --supply-chain-sbom-evidence)
      SUPPLY_CHAIN_SBOM_EVIDENCE="$2"
      shift 2
      ;;
    --supply-chain-sbom-max-age-hours)
      SUPPLY_CHAIN_SBOM_MAX_AGE_HOURS="$2"
      shift 2
      ;;
    --root)
      ROOT="$2"
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

if [[ -z "$CHAT_CONFIG" ]]; then
  CHAT_CONFIG="$ROOT/chat/chat_server/chat.yml"
fi

if [[ "$ENFORCE_V2D_STAGE_ACCEPTANCE" == "true" ]]; then
  if [[ -z "$V2D_REGRESSION_EVIDENCE" ]]; then
    V2D_REGRESSION_EVIDENCE="$ROOT/docs/loadtest/evidence/v2d_regression.env"
  fi
  if [[ -z "$V2D_LOAD_SUMMARY" ]]; then
    V2D_LOAD_SUMMARY="$ROOT/docs/loadtest/evidence/v2d_preprod_summary.env"
  fi
  if [[ -z "$V2D_REPORT_OUT" ]]; then
    V2D_REPORT_OUT="$ROOT/docs/loadtest/evidence/V2-D阶段验收报告-$(date +%F)-from-preflight.md"
  fi
fi

if [[ "$ENFORCE_AI_JUDGE_M7_ACCEPTANCE" == "true" ]]; then
  if [[ -z "$AI_JUDGE_M7_REGRESSION_EVIDENCE" ]]; then
    AI_JUDGE_M7_REGRESSION_EVIDENCE="$ROOT/docs/loadtest/evidence/ai_judge_m7_regression.env"
  fi
  if [[ -z "$AI_JUDGE_M7_PREPROD_SUMMARY" ]]; then
    AI_JUDGE_M7_PREPROD_SUMMARY="$ROOT/docs/loadtest/evidence/ai_judge_m7_preprod_summary.env"
  fi
  if [[ -z "$AI_JUDGE_M7_FAULT_MATRIX" ]]; then
    AI_JUDGE_M7_FAULT_MATRIX="$ROOT/docs/loadtest/evidence/ai_judge_m7_fault_matrix.env"
  fi
  if [[ -z "$AI_JUDGE_M7_REPORT_OUT" ]]; then
    AI_JUDGE_M7_REPORT_OUT="$ROOT/docs/loadtest/evidence/AI裁判M7阶段验收报告-$(date +%F)-from-preflight.md"
  fi
fi

if [[ "$ENFORCE_SUPPLY_CHAIN_SECURITY" == "true" ]]; then
  if [[ -z "$SUPPLY_CHAIN_REPORT_OUT" ]]; then
    SUPPLY_CHAIN_REPORT_OUT="$ROOT/docs/loadtest/evidence/供应链安全门禁报告-$(date +%F)-from-preflight.md"
  fi
  if [[ -z "$SUPPLY_CHAIN_GATE_SCRIPT" ]]; then
    SUPPLY_CHAIN_GATE_SCRIPT="$ROOT/scripts/release/supply_chain_security_gate.sh"
  fi
  if [[ -z "$SUPPLY_CHAIN_CARGO_ADVISORY_ALLOWLIST" ]]; then
    SUPPLY_CHAIN_CARGO_ADVISORY_ALLOWLIST="$ROOT/scripts/release/security_allowlists/cargo_deny_advisories_allowlist.csv"
  fi
  if [[ -z "$SUPPLY_CHAIN_PIP_AUDIT_ALLOWLIST" ]]; then
    SUPPLY_CHAIN_PIP_AUDIT_ALLOWLIST="$ROOT/scripts/release/security_allowlists/pip_audit_vulns_allowlist.csv"
  fi
fi

if [[ "$ENFORCE_SUPPLY_CHAIN_CHAOS_EVIDENCE" == "true" ]]; then
  if [[ -z "$SUPPLY_CHAIN_CHAOS_EVIDENCE" ]]; then
    SUPPLY_CHAIN_CHAOS_EVIDENCE="$ROOT/docs/loadtest/evidence/supply_chain_preprod_chaos.env"
  fi
fi

if [[ "$ENFORCE_SUPPLY_CHAIN_SBOM_ATTESTATION" == "true" ]]; then
  if [[ -z "$SUPPLY_CHAIN_SBOM_EVIDENCE" ]]; then
    SUPPLY_CHAIN_SBOM_EVIDENCE="$ROOT/docs/loadtest/evidence/supply_chain_sbom_attestation.env"
  fi
fi

RUNTIME_ENV="$(trim "$RUNTIME_ENV")"
IS_PRODUCTION="false"
if is_production_env "$RUNTIME_ENV"; then
  IS_PRODUCTION="true"
fi

echo "== App Store release preflight =="
echo "root: $ROOT"
echo "runtime_env: $RUNTIME_ENV (production=$IS_PRODUCTION)"
echo

if [[ ! -f "$CHAT_CONFIG" ]]; then
  mark_fail "chat config not found: $CHAT_CONFIG"
else
  payment_mode_raw="$(read_yaml_scalar_in_section "$CHAT_CONFIG" "payment" "verify_mode")"
  payment_mode="$(normalize_payment_mode "$(strip_quotes "$payment_mode_raw")")"
  apple_prod_url="$(strip_quotes "$(read_yaml_scalar_in_section "$CHAT_CONFIG" "payment" "apple_verify_url_prod")")"
  apple_sandbox_url="$(strip_quotes "$(read_yaml_scalar_in_section "$CHAT_CONFIG" "payment" "apple_verify_url_sandbox")")"

  if [[ "$payment_mode" == "mock" && "$IS_PRODUCTION" == "true" ]]; then
    mark_fail "chat_server payment.verify_mode=mock is forbidden in production"
  else
    mark_pass "chat_server payment.verify_mode=$payment_mode"
  fi

  if [[ "$payment_mode" == "apple" ]]; then
    if [[ -z "$apple_prod_url" ]]; then
      mark_fail "chat_server payment.apple_verify_url_prod is empty"
    else
      mark_pass "chat_server apple_verify_url_prod configured"
    fi
    if [[ -z "$apple_sandbox_url" ]]; then
      mark_fail "chat_server payment.apple_verify_url_sandbox is empty"
    else
      mark_pass "chat_server apple_verify_url_sandbox configured"
    fi
  fi
fi

if [[ -z "$TAURI_APP_CONFIG" ]]; then
  mark_warn "tauri app.yml is not provided; skipped native IAP release checks"
elif [[ ! -f "$TAURI_APP_CONFIG" ]]; then
  mark_fail "tauri app.yml not found: $TAURI_APP_CONFIG"
else
  iap_mode_raw="$(read_yaml_scalar_in_section "$TAURI_APP_CONFIG" "iap" "purchase_mode")"
  iap_mode="$(normalize_iap_purchase_mode "$(strip_quotes "$iap_mode_raw")")"
  iap_bridge_bin="$(strip_quotes "$(read_yaml_scalar_nested "$TAURI_APP_CONFIG" "iap" "native_bridge" "bin")")"

  iap_allowed_products=()
  while IFS= read -r line; do
    line="$(trim "$line")"
    if [[ -n "$line" ]]; then
      iap_allowed_products+=("$line")
    fi
  done < <(read_yaml_list_items "$TAURI_APP_CONFIG" "iap" "allowed_product_ids")

  iap_args=()
  while IFS= read -r line; do
    line="$(trim "$line")"
    if [[ -n "$line" ]]; then
      iap_args+=("$line")
    fi
  done < <(read_yaml_list_items_nested "$TAURI_APP_CONFIG" "iap" "native_bridge" "args")

  has_simulate_arg="false"
  for arg in "${iap_args[@]-}"; do
    normalized_arg="$(to_lower "$(trim "$arg")")"
    if [[ "$normalized_arg" == "--simulate" || "$normalized_arg" == "-simulate" ]]; then
      has_simulate_arg="true"
      break
    fi
  done

  if [[ "$iap_mode" == "mock" && "$IS_PRODUCTION" == "true" ]]; then
    mark_fail "tauri iap.purchase_mode=mock is forbidden in production"
  else
    mark_pass "tauri iap.purchase_mode=$iap_mode"
  fi

  if [[ "$iap_mode" == "native" ]]; then
    if [[ -z "$iap_bridge_bin" ]]; then
      mark_fail "tauri iap.native_bridge.bin is empty"
    else
      mark_pass "tauri iap.native_bridge.bin configured"
    fi

    if [[ "$IS_PRODUCTION" == "true" ]]; then
      if [[ -n "$iap_bridge_bin" && "${iap_bridge_bin:0:1}" != "/" ]]; then
        mark_fail "tauri iap.native_bridge.bin must be absolute in production"
      else
        mark_pass "tauri iap.native_bridge.bin is absolute"
      fi

      if [[ "$has_simulate_arg" == "true" ]]; then
        mark_fail "tauri iap.native_bridge.args contains --simulate in production"
      else
        mark_pass "tauri iap.native_bridge.args has no --simulate"
      fi

      if [[ "${#iap_allowed_products[@]}" -eq 0 ]]; then
        mark_fail "tauri iap.allowed_product_ids is empty in production"
      else
        mark_pass "tauri iap.allowed_product_ids count=${#iap_allowed_products[@]}"
      fi
    fi

    for product_id in "${iap_allowed_products[@]-}"; do
      if [[ ! "$product_id" =~ ^[A-Za-z0-9._-]{1,64}$ ]]; then
        mark_fail "tauri iap.allowed_product_ids contains invalid value: $product_id"
      fi
    done
  fi
fi

if [[ -n "$AI_JUDGE_ENV" && ! -f "$AI_JUDGE_ENV" ]]; then
  mark_fail "ai judge env file not found: $AI_JUDGE_ENV"
else
  ai_provider="$(normalize_provider "$(read_env_value "AI_JUDGE_PROVIDER" "$AI_JUDGE_ENV")")"
  ai_openai_key="$(read_env_value "OPENAI_API_KEY" "$AI_JUDGE_ENV")"
  ai_fallback_to_mock="$(normalize_bool "$(read_env_value "AI_JUDGE_OPENAI_FALLBACK_TO_MOCK" "$AI_JUDGE_ENV")")"

  if [[ "$IS_PRODUCTION" == "true" ]]; then
    if [[ "$ai_provider" == "mock" ]]; then
      mark_fail "ai_judge AI_JUDGE_PROVIDER=mock is forbidden in production"
    else
      mark_pass "ai_judge provider=$ai_provider"
    fi

    if [[ "$ai_fallback_to_mock" == "true" ]]; then
      mark_fail "ai_judge AI_JUDGE_OPENAI_FALLBACK_TO_MOCK=true is forbidden in production"
    else
      mark_pass "ai_judge openai fallback to mock disabled"
    fi

    if [[ "$ai_provider" == "openai" && -z "$(trim "$ai_openai_key")" ]]; then
      mark_fail "ai_judge OPENAI_API_KEY is empty in production"
    elif [[ "$ai_provider" == "openai" ]]; then
      mark_pass "ai_judge OPENAI_API_KEY configured"
    fi
  else
    mark_pass "ai_judge production guard skipped for non-production runtime"
  fi
fi

if [[ "$ENFORCE_V2D_STAGE_ACCEPTANCE" == "true" ]]; then
  v2d_gate_script="$ROOT/scripts/release/v2d_stage_acceptance_gate.sh"
  if [[ ! -f "$v2d_gate_script" ]]; then
    mark_fail "v2d gate script not found: $v2d_gate_script"
  else
    v2d_args=(
      --root "$ROOT"
      --regression-evidence "$V2D_REGRESSION_EVIDENCE"
      --load-summary "$V2D_LOAD_SUMMARY"
      --report-out "$V2D_REPORT_OUT"
    )
    if [[ "$V2D_ALLOW_MISSING_SCENARIOS" == "true" ]]; then
      v2d_args+=(--allow-missing-scenarios)
    fi

    if bash "$v2d_gate_script" "${v2d_args[@]}"; then
      mark_pass "v2d stage acceptance gate passed"
    else
      mark_fail "v2d stage acceptance gate failed"
    fi
  fi
fi

if [[ "$ENFORCE_AI_JUDGE_M7_ACCEPTANCE" == "true" ]]; then
  ai_judge_m7_gate_script="$ROOT/scripts/release/ai_judge_m7_stage_acceptance_gate.sh"
  if [[ ! -f "$ai_judge_m7_gate_script" ]]; then
    mark_fail "ai judge m7 gate script not found: $ai_judge_m7_gate_script"
  else
    ai_judge_m7_args=(
      --root "$ROOT"
      --regression-evidence "$AI_JUDGE_M7_REGRESSION_EVIDENCE"
      --preprod-summary "$AI_JUDGE_M7_PREPROD_SUMMARY"
      --fault-matrix "$AI_JUDGE_M7_FAULT_MATRIX"
      --report-out "$AI_JUDGE_M7_REPORT_OUT"
    )
    if [[ "$AI_JUDGE_M7_ALLOW_MISSING_SCENARIOS" == "true" ]]; then
      ai_judge_m7_args+=(--allow-missing-scenarios)
    fi

    if bash "$ai_judge_m7_gate_script" "${ai_judge_m7_args[@]}"; then
      mark_pass "ai judge m7 stage acceptance gate passed"
    else
      mark_fail "ai judge m7 stage acceptance gate failed"
    fi
  fi
fi

if [[ "$ENFORCE_SUPPLY_CHAIN_SECURITY" == "true" ]]; then
  if [[ ! -f "$SUPPLY_CHAIN_GATE_SCRIPT" ]]; then
    mark_fail "supply chain gate script not found: $SUPPLY_CHAIN_GATE_SCRIPT"
  else
    supply_chain_args=(
      --root "$ROOT"
      --report-out "$SUPPLY_CHAIN_REPORT_OUT"
      --cargo-advisory-allowlist "$SUPPLY_CHAIN_CARGO_ADVISORY_ALLOWLIST"
      --pip-audit-allowlist "$SUPPLY_CHAIN_PIP_AUDIT_ALLOWLIST"
    )
    if [[ "$SUPPLY_CHAIN_ALLOW_MISSING_TOOLS" == "true" ]]; then
      supply_chain_args+=(--allow-missing-tools)
    fi

    if bash "$SUPPLY_CHAIN_GATE_SCRIPT" "${supply_chain_args[@]}"; then
      mark_pass "supply chain security gate passed"
    else
      mark_fail "supply chain security gate failed"
    fi
  fi
fi

if [[ "$ENFORCE_SUPPLY_CHAIN_CHAOS_EVIDENCE" == "true" ]]; then
  if [[ ! "$SUPPLY_CHAIN_CHAOS_MAX_AGE_HOURS" =~ ^[0-9]+$ ]]; then
    mark_fail "supply chain chaos max age must be numeric hours: $SUPPLY_CHAIN_CHAOS_MAX_AGE_HOURS"
  elif [[ "$SUPPLY_CHAIN_CHAOS_MAX_AGE_HOURS" -eq 0 ]]; then
    mark_fail "supply chain chaos max age must be greater than zero"
  elif [[ ! -f "$SUPPLY_CHAIN_CHAOS_EVIDENCE" ]]; then
    mark_fail "supply chain chaos evidence file not found: $SUPPLY_CHAIN_CHAOS_EVIDENCE"
  else
    scenario_advisory="$(to_lower "$(trim "$(read_env_value "SCENARIO_ADVISORY_SOURCE_UNAVAILABLE" "$SUPPLY_CHAIN_CHAOS_EVIDENCE")")")"
    scenario_pip_audit="$(to_lower "$(trim "$(read_env_value "SCENARIO_PIP_AUDIT_MISSING" "$SUPPLY_CHAIN_CHAOS_EVIDENCE")")")"
    scenario_allowlist="$(to_lower "$(trim "$(read_env_value "SCENARIO_ALLOWLIST_EXPIRED" "$SUPPLY_CHAIN_CHAOS_EVIDENCE")")")"
    chaos_last_run_at="$(trim "$(read_env_value "CHAOS_LAST_RUN_AT" "$SUPPLY_CHAIN_CHAOS_EVIDENCE")")"

    if [[ "$scenario_advisory" != "pass" ]]; then
      mark_fail "supply chain chaos scenario advisory_source_unavailable is not pass"
    else
      mark_pass "supply chain chaos scenario advisory_source_unavailable=pass"
    fi

    if [[ "$scenario_pip_audit" != "pass" ]]; then
      mark_fail "supply chain chaos scenario pip_audit_missing is not pass"
    else
      mark_pass "supply chain chaos scenario pip_audit_missing=pass"
    fi

    if [[ "$scenario_allowlist" != "pass" ]]; then
      mark_fail "supply chain chaos scenario allowlist_expired is not pass"
    else
      mark_pass "supply chain chaos scenario allowlist_expired=pass"
    fi

    if [[ -z "$chaos_last_run_at" ]]; then
      mark_fail "supply chain chaos evidence missing CHAOS_LAST_RUN_AT"
    else
      chaos_last_run_epoch=""
      if ! chaos_last_run_epoch="$(parse_epoch_from_iso8601_utc "$chaos_last_run_at")"; then
        mark_fail "supply chain chaos evidence CHAOS_LAST_RUN_AT is invalid: $chaos_last_run_at"
      else
        now_epoch="$(date -u +%s)"
        if [[ "$chaos_last_run_epoch" -gt "$now_epoch" ]]; then
          mark_fail "supply chain chaos evidence CHAOS_LAST_RUN_AT is in the future: $chaos_last_run_at"
        else
          chaos_age_secs=$((now_epoch - chaos_last_run_epoch))
          chaos_max_age_secs=$((SUPPLY_CHAIN_CHAOS_MAX_AGE_HOURS * 3600))
          if [[ "$chaos_age_secs" -gt "$chaos_max_age_secs" ]]; then
            mark_fail "supply chain chaos evidence is stale: age_seconds=$chaos_age_secs max_age_seconds=$chaos_max_age_secs"
          else
            mark_pass "supply chain chaos evidence freshness ok: age_seconds=$chaos_age_secs max_age_seconds=$chaos_max_age_secs"
          fi
        fi
      fi
    fi
  fi
fi

if [[ "$ENFORCE_SUPPLY_CHAIN_SBOM_ATTESTATION" == "true" ]]; then
  if [[ ! "$SUPPLY_CHAIN_SBOM_MAX_AGE_HOURS" =~ ^[0-9]+$ ]]; then
    mark_fail "supply chain sbom max age must be numeric hours: $SUPPLY_CHAIN_SBOM_MAX_AGE_HOURS"
  elif [[ "$SUPPLY_CHAIN_SBOM_MAX_AGE_HOURS" -eq 0 ]]; then
    mark_fail "supply chain sbom max age must be greater than zero"
  elif [[ ! -f "$SUPPLY_CHAIN_SBOM_EVIDENCE" ]]; then
    mark_fail "supply chain sbom evidence file not found: $SUPPLY_CHAIN_SBOM_EVIDENCE"
  else
    sbom_generated_at="$(trim "$(read_env_value "SBOM_GENERATED_AT" "$SUPPLY_CHAIN_SBOM_EVIDENCE")")"
    sbom_rust_path="$(trim "$(read_env_value "SBOM_RUST_PATH" "$SUPPLY_CHAIN_SBOM_EVIDENCE")")"
    sbom_python_path="$(trim "$(read_env_value "SBOM_PYTHON_PATH" "$SUPPLY_CHAIN_SBOM_EVIDENCE")")"
    sbom_license_path="$(trim "$(read_env_value "SBOM_LICENSE_ATTESTATION_PATH" "$SUPPLY_CHAIN_SBOM_EVIDENCE")")"
    sbom_rust_sha_expected="$(trim "$(read_env_value "SBOM_RUST_SHA256" "$SUPPLY_CHAIN_SBOM_EVIDENCE")")"
    sbom_python_sha_expected="$(trim "$(read_env_value "SBOM_PYTHON_SHA256" "$SUPPLY_CHAIN_SBOM_EVIDENCE")")"
    sbom_license_sha_expected="$(trim "$(read_env_value "SBOM_LICENSE_SHA256" "$SUPPLY_CHAIN_SBOM_EVIDENCE")")"

    sbom_license_rust_status="$(to_lower "$(trim "$(read_env_value "SBOM_LICENSE_CHECK_RUST" "$SUPPLY_CHAIN_SBOM_EVIDENCE")")")"
    sbom_license_python_status="$(to_lower "$(trim "$(read_env_value "SBOM_LICENSE_CHECK_PYTHON_PINNED" "$SUPPLY_CHAIN_SBOM_EVIDENCE")")")"

    if [[ "$sbom_license_rust_status" != "pass" ]]; then
      mark_fail "supply chain sbom license check rust is not pass"
    else
      mark_pass "supply chain sbom license check rust=pass"
    fi

    if [[ "$sbom_license_python_status" != "pass" ]]; then
      mark_fail "supply chain sbom license check python pinned is not pass"
    else
      mark_pass "supply chain sbom license check python pinned=pass"
    fi

    if [[ -z "$sbom_generated_at" ]]; then
      mark_fail "supply chain sbom evidence missing SBOM_GENERATED_AT"
    else
      sbom_generated_epoch=""
      if ! sbom_generated_epoch="$(parse_epoch_from_iso8601_utc "$sbom_generated_at")"; then
        mark_fail "supply chain sbom evidence SBOM_GENERATED_AT is invalid: $sbom_generated_at"
      else
        now_epoch="$(date -u +%s)"
        if [[ "$sbom_generated_epoch" -gt "$now_epoch" ]]; then
          mark_fail "supply chain sbom evidence SBOM_GENERATED_AT is in the future: $sbom_generated_at"
        else
          sbom_age_secs=$((now_epoch - sbom_generated_epoch))
          sbom_max_age_secs=$((SUPPLY_CHAIN_SBOM_MAX_AGE_HOURS * 3600))
          if [[ "$sbom_age_secs" -gt "$sbom_max_age_secs" ]]; then
            mark_fail "supply chain sbom evidence is stale: age_seconds=$sbom_age_secs max_age_seconds=$sbom_max_age_secs"
          else
            mark_pass "supply chain sbom evidence freshness ok: age_seconds=$sbom_age_secs max_age_seconds=$sbom_max_age_secs"
          fi
        fi
      fi
    fi

    if [[ -z "$sbom_rust_path" || ! -f "$sbom_rust_path" ]]; then
      mark_fail "supply chain sbom rust file missing: $sbom_rust_path"
    else
      mark_pass "supply chain sbom rust file present"
      if [[ -z "$sbom_rust_sha_expected" ]]; then
        mark_fail "supply chain sbom rust sha256 missing in evidence"
      else
        if sbom_rust_sha_actual="$(sha256_file "$sbom_rust_path" 2>/dev/null)"; then
          if [[ "$sbom_rust_sha_actual" == "$sbom_rust_sha_expected" ]]; then
            mark_pass "supply chain sbom rust sha256 matched"
          else
            mark_fail "supply chain sbom rust sha256 mismatch"
          fi
        else
          mark_fail "supply chain sbom rust sha256 compute failed"
        fi
      fi
    fi

    if [[ -z "$sbom_python_path" || ! -f "$sbom_python_path" ]]; then
      mark_fail "supply chain sbom python file missing: $sbom_python_path"
    else
      mark_pass "supply chain sbom python file present"
      if [[ -z "$sbom_python_sha_expected" ]]; then
        mark_fail "supply chain sbom python sha256 missing in evidence"
      else
        if sbom_python_sha_actual="$(sha256_file "$sbom_python_path" 2>/dev/null)"; then
          if [[ "$sbom_python_sha_actual" == "$sbom_python_sha_expected" ]]; then
            mark_pass "supply chain sbom python sha256 matched"
          else
            mark_fail "supply chain sbom python sha256 mismatch"
          fi
        else
          mark_fail "supply chain sbom python sha256 compute failed"
        fi
      fi
    fi

    if [[ -z "$sbom_license_path" || ! -f "$sbom_license_path" ]]; then
      mark_fail "supply chain sbom license attestation file missing: $sbom_license_path"
    else
      mark_pass "supply chain sbom license attestation file present"
      if [[ -z "$sbom_license_sha_expected" ]]; then
        mark_fail "supply chain sbom license attestation sha256 missing in evidence"
      else
        if sbom_license_sha_actual="$(sha256_file "$sbom_license_path" 2>/dev/null)"; then
          if [[ "$sbom_license_sha_actual" == "$sbom_license_sha_expected" ]]; then
            mark_pass "supply chain sbom license attestation sha256 matched"
          else
            mark_fail "supply chain sbom license attestation sha256 mismatch"
          fi
        else
          mark_fail "supply chain sbom license attestation sha256 compute failed"
        fi
      fi
    fi
  fi
fi

echo "---- PASS ----"
for item in "${PASS_ITEMS[@]-}"; do
  [[ -z "$item" ]] && continue
  echo "[PASS] $item"
done
if [[ "$PASS_COUNT" -eq 0 ]]; then
  echo "(none)"
fi
echo

echo "---- WARN ----"
for item in "${WARN_ITEMS[@]-}"; do
  [[ -z "$item" ]] && continue
  echo "[WARN] $item"
done
if [[ "$WARN_COUNT" -eq 0 ]]; then
  echo "(none)"
fi
echo

echo "---- FAIL ----"
for item in "${FAIL_ITEMS[@]-}"; do
  [[ -z "$item" ]] && continue
  echo "[FAIL] $item"
done
if [[ "$FAIL_COUNT" -eq 0 ]]; then
  echo "(none)"
fi
echo

if [[ "$FAIL_COUNT" -gt 0 ]]; then
  echo "preflight result: FAILED ($FAIL_COUNT issue(s))"
  exit 1
fi

echo "preflight result: PASSED"
