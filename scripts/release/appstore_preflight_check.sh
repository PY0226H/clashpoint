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
  --root <path>                Repo root path (default: git top-level or cwd)
  -h, --help                   Show this help

Notes:
  1) Production checks are enabled when runtime env is prod|production.
  2) AI judge values are read from --ai-judge-env first, then process env.
  3) Tauri checks are skipped when --tauri-app-config is not provided.
  4) V2-D gate is optional and runs only when --enforce-v2d-stage-acceptance is set.
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
    V2D_REPORT_OUT="$ROOT/docs/dev_plan/V2-D阶段验收报告-$(date +%F)-from-preflight.md"
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
