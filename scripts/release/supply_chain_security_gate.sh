#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage:
  supply_chain_security_gate.sh [options]

Options:
  --root <path>                   Repo root path (default: git top-level or cwd)
  --report-out <path>             Markdown report output path
                                  default: docs/loadtest/evidence/供应链安全门禁报告-<YYYY-MM-DD>.md
  --allow-missing-tools           Downgrade missing tool checks to warning
  --cargo-audit-bin <path|name>   cargo-audit binary (default: cargo-audit)
  --cargo-deny-bin <path|name>    cargo-deny binary (default: cargo-deny)
  --cargo-advisory-allowlist <path>
                                  CSV allowlist for cargo deny advisory ignores
                                  default: scripts/release/security_allowlists/cargo_deny_advisories_allowlist.csv
  --python-bin <path>             Python binary for pip-audit
                                  default: ai_judge_service/.venv/bin/python
  --python-requirements <path>    Requirements file for pip-audit
                                  default: ai_judge_service/requirements.txt
  --pip-audit-allowlist <path>    CSV allowlist for pip-audit ignore vuln IDs
                                  default: scripts/release/security_allowlists/pip_audit_vulns_allowlist.csv
  --rust-targets <csv>            Rust workspace dirs to scan
                                  default: chat,frontend/apps/desktop/src-tauri,swiftide-pgvector
  --skip-rust                     Skip Rust supply-chain checks
  --skip-python                   Skip Python supply-chain checks
  -h, --help                      Show this help

CSV schema:
  cargo advisory allowlist:
    advisory_id,target,expires_on,owner,reason
  pip audit allowlist:
    vuln_id,package,expires_on,owner,reason
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

tool_exists() {
  local tool="$1"
  if [[ "$tool" == */* ]]; then
    [[ -x "$tool" ]]
    return
  fi
  command -v "$tool" >/dev/null 2>&1
}

run_in_dir() {
  local dir="$1"
  shift
  local log_file
  log_file="$(mktemp)"
  if (cd "$dir" && "$@" >"$log_file" 2>&1); then
    rm -f "$log_file"
    return 0
  fi
  cat "$log_file" >&2
  rm -f "$log_file"
  return 1
}

date_to_epoch() {
  local value="$1"
  if date -d "$value" +%s >/dev/null 2>&1; then
    date -d "$value" +%s
    return 0
  fi
  if date -j -f "%Y-%m-%d" "$value" +%s >/dev/null 2>&1; then
    date -j -f "%Y-%m-%d" "$value" +%s
    return 0
  fi
  return 1
}

is_expired_date() {
  local value="$1"
  local epoch
  epoch="$(date_to_epoch "$value" 2>/dev/null || true)"
  if [[ -z "$epoch" ]]; then
    return 2
  fi
  local end_of_day=$((epoch + 86399))
  if [[ "$NOW_EPOCH" -gt "$end_of_day" ]]; then
    return 0
  fi
  return 1
}

extract_cargo_ignore_ids() {
  local deny_file="$1"
  awk '
    BEGIN { in_advisories = 0; in_ignore = 0 }
    /^\[[^]]+\][[:space:]]*$/ {
      in_advisories = ($0 == "[advisories]")
      in_ignore = 0
    }
    {
      if (!in_advisories) {
        next
      }
      line = $0
      sub(/#.*/, "", line)
      if (!in_ignore && line ~ /^[[:space:]]*ignore[[:space:]]*=/) {
        in_ignore = 1
      }
      if (in_ignore) {
        rest = line
        while (match(rest, /RUSTSEC-[0-9]{4}-[0-9]{4}/)) {
          print substr(rest, RSTART, RLENGTH)
          rest = substr(rest, RSTART + RLENGTH)
        }
        if (line ~ /\]/) {
          in_ignore = 0
        }
      }
    }
  ' "$deny_file" | sort -u
}

CARGO_ALLOWLIST_ROW_COUNT=0
CARGO_ALLOWLIST_ACTIVE_COUNT=0
PIP_ALLOWLIST_ROW_COUNT=0
PIP_ALLOWLIST_ACTIVE_COUNT=0
PIP_AUDIT_IGNORE_IDS=()

validate_cargo_allowlist() {
  local file="$1"
  CARGO_ALLOWLIST_ROW_COUNT=0
  CARGO_ALLOWLIST_ACTIVE_COUNT=0

  if [[ ! -f "$file" ]]; then
    mark_fail "cargo advisory allowlist missing: $file"
    return
  fi

  local line_no=0
  while IFS= read -r raw_line || [[ -n "$raw_line" ]]; do
    line_no=$((line_no + 1))
    local line
    line="$(trim "$raw_line")"
    [[ -z "$line" ]] && continue
    [[ "${line:0:1}" == "#" ]] && continue

    local advisory_id target expires_on owner reason extra
    IFS=',' read -r advisory_id target expires_on owner reason extra <<<"$line"
    advisory_id="$(strip_quotes "${advisory_id:-}")"
    target="$(strip_quotes "${target:-}")"
    expires_on="$(strip_quotes "${expires_on:-}")"
    owner="$(strip_quotes "${owner:-}")"
    reason="$(strip_quotes "${reason:-}")"
    extra="$(strip_quotes "${extra:-}")"

    CARGO_ALLOWLIST_ROW_COUNT=$((CARGO_ALLOWLIST_ROW_COUNT + 1))

    if [[ -n "$extra" ]]; then
      mark_fail "cargo allowlist row has too many fields [$file:$line_no]"
      continue
    fi
    if [[ ! "$advisory_id" =~ ^RUSTSEC-[0-9]{4}-[0-9]{4}$ ]]; then
      mark_fail "cargo allowlist advisory_id invalid [$file:$line_no]"
      continue
    fi
    if [[ -z "$target" ]]; then
      mark_fail "cargo allowlist target missing [$file:$line_no]"
      continue
    fi
    if [[ -z "$owner" || -z "$reason" ]]; then
      mark_fail "cargo allowlist owner/reason missing [$file:$line_no]"
      continue
    fi

    local expired_state=0
    if is_expired_date "$expires_on"; then
      expired_state=0
    else
      expired_state=$?
    fi
    if [[ "$expired_state" -eq 2 ]]; then
      mark_fail "cargo allowlist expires_on invalid [$file:$line_no]"
      continue
    fi
    if [[ "$expired_state" -eq 0 ]]; then
      mark_fail "cargo allowlist expired [$advisory_id target=$target expires_on=$expires_on]"
      continue
    fi

    CARGO_ALLOWLIST_ACTIVE_COUNT=$((CARGO_ALLOWLIST_ACTIVE_COUNT + 1))
  done <"$file"

  if [[ "$CARGO_ALLOWLIST_ROW_COUNT" -eq 0 ]]; then
    mark_warn "cargo advisory allowlist empty: $file"
  else
    mark_pass "cargo advisory allowlist validated (rows=$CARGO_ALLOWLIST_ROW_COUNT active=$CARGO_ALLOWLIST_ACTIVE_COUNT)"
  fi
}

cargo_allowlist_has_active_entry() {
  local file="$1"
  local advisory_id="$2"
  local target="$3"
  local wildcard_match=1

  while IFS= read -r raw_line || [[ -n "$raw_line" ]]; do
    local line
    line="$(trim "$raw_line")"
    [[ -z "$line" ]] && continue
    [[ "${line:0:1}" == "#" ]] && continue

    local row_advisory row_target expires_on owner reason extra
    IFS=',' read -r row_advisory row_target expires_on owner reason extra <<<"$line"
    row_advisory="$(strip_quotes "${row_advisory:-}")"
    row_target="$(strip_quotes "${row_target:-}")"
    expires_on="$(strip_quotes "${expires_on:-}")"

    [[ "$row_advisory" != "$advisory_id" ]] && continue

    if is_expired_date "$expires_on"; then
      continue
    elif [[ "$?" -eq 2 ]]; then
      continue
    fi

    if [[ "$row_target" == "$target" ]]; then
      return 0
    fi
    if [[ "$row_target" == "*" ]]; then
      wildcard_match=0
    fi
  done <"$file"

  return "$wildcard_match"
}

collect_active_cargo_allowlist_ids() {
  local file="$1"
  local target="$2"

  while IFS= read -r raw_line || [[ -n "$raw_line" ]]; do
    local line
    line="$(trim "$raw_line")"
    [[ -z "$line" ]] && continue
    [[ "${line:0:1}" == "#" ]] && continue

    local row_advisory row_target expires_on owner reason extra
    IFS=',' read -r row_advisory row_target expires_on owner reason extra <<<"$line"
    row_advisory="$(strip_quotes "${row_advisory:-}")"
    row_target="$(strip_quotes "${row_target:-}")"
    expires_on="$(strip_quotes "${expires_on:-}")"

    [[ "$row_advisory" =~ ^RUSTSEC-[0-9]{4}-[0-9]{4}$ ]] || continue
    if is_expired_date "$expires_on"; then
      continue
    elif [[ "$?" -eq 2 ]]; then
      continue
    fi

    if [[ "$row_target" == "$target" || "$row_target" == "*" ]]; then
      printf '%s\n' "$row_advisory"
    fi
  done <"$file" | sort -u
}

pip_ignore_contains() {
  local needle="$1"
  local item
  for item in "${PIP_AUDIT_IGNORE_IDS[@]-}"; do
    if [[ "$item" == "$needle" ]]; then
      return 0
    fi
  done
  return 1
}

validate_pip_allowlist() {
  local file="$1"
  PIP_ALLOWLIST_ROW_COUNT=0
  PIP_ALLOWLIST_ACTIVE_COUNT=0
  PIP_AUDIT_IGNORE_IDS=()

  if [[ ! -f "$file" ]]; then
    mark_fail "pip-audit allowlist missing: $file"
    return
  fi

  local line_no=0
  while IFS= read -r raw_line || [[ -n "$raw_line" ]]; do
    line_no=$((line_no + 1))
    local line
    line="$(trim "$raw_line")"
    [[ -z "$line" ]] && continue
    [[ "${line:0:1}" == "#" ]] && continue

    local vuln_id package expires_on owner reason extra
    IFS=',' read -r vuln_id package expires_on owner reason extra <<<"$line"
    vuln_id="$(strip_quotes "${vuln_id:-}")"
    package="$(strip_quotes "${package:-}")"
    expires_on="$(strip_quotes "${expires_on:-}")"
    owner="$(strip_quotes "${owner:-}")"
    reason="$(strip_quotes "${reason:-}")"
    extra="$(strip_quotes "${extra:-}")"

    PIP_ALLOWLIST_ROW_COUNT=$((PIP_ALLOWLIST_ROW_COUNT + 1))

    if [[ -n "$extra" ]]; then
      mark_fail "pip-audit allowlist row has too many fields [$file:$line_no]"
      continue
    fi
    if [[ ! "$vuln_id" =~ ^(GHSA|PYSEC|CVE)- ]]; then
      mark_fail "pip-audit allowlist vuln_id invalid [$file:$line_no]"
      continue
    fi
    if [[ -z "$package" || -z "$owner" || -z "$reason" ]]; then
      mark_fail "pip-audit allowlist package/owner/reason missing [$file:$line_no]"
      continue
    fi

    local expired_state=0
    if is_expired_date "$expires_on"; then
      expired_state=0
    else
      expired_state=$?
    fi
    if [[ "$expired_state" -eq 2 ]]; then
      mark_fail "pip-audit allowlist expires_on invalid [$file:$line_no]"
      continue
    fi
    if [[ "$expired_state" -eq 0 ]]; then
      mark_fail "pip-audit allowlist expired [$vuln_id package=$package expires_on=$expires_on]"
      continue
    fi

    PIP_ALLOWLIST_ACTIVE_COUNT=$((PIP_ALLOWLIST_ACTIVE_COUNT + 1))
    if ! pip_ignore_contains "$vuln_id"; then
      PIP_AUDIT_IGNORE_IDS+=("$vuln_id")
    fi
  done <"$file"

  if [[ "$PIP_ALLOWLIST_ROW_COUNT" -eq 0 ]]; then
    mark_warn "pip-audit allowlist empty: $file"
  else
    mark_pass "pip-audit allowlist validated (rows=$PIP_ALLOWLIST_ROW_COUNT active=$PIP_ALLOWLIST_ACTIVE_COUNT)"
  fi
}

ROOT=""
REPORT_OUT=""
ALLOW_MISSING_TOOLS="false"
CARGO_AUDIT_BIN="cargo-audit"
CARGO_DENY_BIN="cargo-deny"
CARGO_ADVISORY_ALLOWLIST=""
PYTHON_BIN=""
PYTHON_REQUIREMENTS=""
PIP_AUDIT_ALLOWLIST=""
RUST_TARGETS_CSV="chat,frontend/apps/desktop/src-tauri,swiftide-pgvector"
SKIP_RUST="false"
SKIP_PYTHON="false"
CARGO_AUDIT_USE_SUBCOMMAND="false"

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
    --allow-missing-tools)
      ALLOW_MISSING_TOOLS="true"
      shift
      ;;
    --cargo-audit-bin)
      CARGO_AUDIT_BIN="$2"
      shift 2
      ;;
    --cargo-deny-bin)
      CARGO_DENY_BIN="$2"
      shift 2
      ;;
    --cargo-advisory-allowlist)
      CARGO_ADVISORY_ALLOWLIST="$2"
      shift 2
      ;;
    --python-bin)
      PYTHON_BIN="$2"
      shift 2
      ;;
    --python-requirements)
      PYTHON_REQUIREMENTS="$2"
      shift 2
      ;;
    --pip-audit-allowlist)
      PIP_AUDIT_ALLOWLIST="$2"
      shift 2
      ;;
    --rust-targets)
      RUST_TARGETS_CSV="$2"
      shift 2
      ;;
    --skip-rust)
      SKIP_RUST="true"
      shift
      ;;
    --skip-python)
      SKIP_PYTHON="true"
      shift
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

if [[ -z "$REPORT_OUT" ]]; then
  REPORT_OUT="$ROOT/docs/loadtest/evidence/供应链安全门禁报告-$(date +%F).md"
fi
if [[ -z "$PYTHON_BIN" ]]; then
  PYTHON_BIN="$ROOT/ai_judge_service/.venv/bin/python"
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

NOW_EPOCH="$(date +%s)"

mkdir -p "$(dirname "$REPORT_OUT")"

echo "== Supply chain security gate =="
echo "root: $ROOT"
echo "report_out: $REPORT_OUT"
echo "allow_missing_tools: $ALLOW_MISSING_TOOLS"
echo "cargo_allowlist: $CARGO_ADVISORY_ALLOWLIST"
echo "pip_allowlist: $PIP_AUDIT_ALLOWLIST"
echo

if [[ "$SKIP_RUST" == "false" ]]; then
  validate_cargo_allowlist "$CARGO_ADVISORY_ALLOWLIST"
else
  mark_warn "rust checks skipped (--skip-rust)"
fi

if [[ "$SKIP_PYTHON" == "false" ]]; then
  validate_pip_allowlist "$PIP_AUDIT_ALLOWLIST"
else
  mark_warn "python checks skipped (--skip-python)"
fi

if [[ "$SKIP_RUST" == "false" ]]; then
  if ! tool_exists "$CARGO_AUDIT_BIN"; then
    if [[ "$ALLOW_MISSING_TOOLS" == "true" ]]; then
      mark_warn "cargo-audit missing: $CARGO_AUDIT_BIN"
    else
      mark_fail "cargo-audit missing: $CARGO_AUDIT_BIN"
    fi
  fi
  if ! tool_exists "$CARGO_DENY_BIN"; then
    if [[ "$ALLOW_MISSING_TOOLS" == "true" ]]; then
      mark_warn "cargo-deny missing: $CARGO_DENY_BIN"
    else
      mark_fail "cargo-deny missing: $CARGO_DENY_BIN"
    fi
  fi

  if tool_exists "$CARGO_AUDIT_BIN"; then
    if "$CARGO_AUDIT_BIN" audit --help >/dev/null 2>&1; then
      CARGO_AUDIT_USE_SUBCOMMAND="true"
    fi
  fi

  IFS=',' read -r -a rust_targets <<<"$RUST_TARGETS_CSV"
  for target in "${rust_targets[@]}"; do
    target="$(trim "$target")"
    [[ -z "$target" ]] && continue

    target_dir="$ROOT/$target"
    if [[ ! -d "$target_dir" ]]; then
      mark_fail "rust target dir missing: $target_dir"
      continue
    fi

    deny_toml="$target_dir/deny.toml"
    if [[ ! -f "$deny_toml" ]]; then
      mark_fail "cargo deny config missing: $deny_toml"
      continue
    fi

    ignore_found=0
    while IFS= read -r advisory_id; do
      [[ -z "$advisory_id" ]] && continue
      ignore_found=1
      if cargo_allowlist_has_active_entry "$CARGO_ADVISORY_ALLOWLIST" "$advisory_id" "$target"; then
        mark_pass "cargo advisory allowlist matched [$target:$advisory_id]"
      else
        mark_fail "cargo advisory allowlist missing/expired [$target:$advisory_id]"
      fi
    done < <(extract_cargo_ignore_ids "$deny_toml")

    if [[ "$ignore_found" -eq 0 ]]; then
      mark_pass "cargo advisory allowlist clean [$target]"
    fi

    if tool_exists "$CARGO_AUDIT_BIN"; then
      cargo_audit_cmd=("$CARGO_AUDIT_BIN")
      if [[ "$CARGO_AUDIT_USE_SUBCOMMAND" == "true" ]]; then
        cargo_audit_cmd+=("audit")
      fi
      cargo_audit_cmd+=("--no-fetch")
      while IFS= read -r allow_id; do
        [[ -z "$allow_id" ]] && continue
        cargo_audit_cmd+=("--ignore" "$allow_id")
      done < <(collect_active_cargo_allowlist_ids "$CARGO_ADVISORY_ALLOWLIST" "$target")

      if run_in_dir "$target_dir" "${cargo_audit_cmd[@]}"; then
        mark_pass "cargo-audit passed [$target]"
      else
        mark_fail "cargo-audit failed [$target]"
      fi
    fi

    if tool_exists "$CARGO_DENY_BIN"; then
      if run_in_dir "$target_dir" "$CARGO_DENY_BIN" check advisories bans sources licenses; then
        mark_pass "cargo-deny passed [$target]"
      else
        mark_fail "cargo-deny failed [$target]"
      fi
    fi
  done
fi

if [[ "$SKIP_PYTHON" == "false" ]]; then
  if [[ ! -f "$PYTHON_REQUIREMENTS" ]]; then
    mark_fail "python requirements not found: $PYTHON_REQUIREMENTS"
  fi

  if ! tool_exists "$PYTHON_BIN"; then
    if [[ "$ALLOW_MISSING_TOOLS" == "true" ]]; then
      mark_warn "python binary missing for pip-audit: $PYTHON_BIN"
    else
      mark_fail "python binary missing for pip-audit: $PYTHON_BIN"
    fi
  fi

  if [[ -f "$PYTHON_REQUIREMENTS" ]] && tool_exists "$PYTHON_BIN"; then
    pip_audit_args=(-m pip_audit -r "$PYTHON_REQUIREMENTS" --progress-spinner off)
    for ignore_vuln in "${PIP_AUDIT_IGNORE_IDS[@]-}"; do
      [[ -z "$ignore_vuln" ]] && continue
      pip_audit_args+=(--ignore-vuln "$ignore_vuln")
    done

    if "$PYTHON_BIN" "${pip_audit_args[@]}" >/tmp/pip_audit_gate.log 2>&1; then
      mark_pass "pip-audit passed [ai_judge_service ignores=${#PIP_AUDIT_IGNORE_IDS[@]}]"
    else
      if grep -Eq 'No module named pip_audit|No module named pip_audit.__main__' /tmp/pip_audit_gate.log; then
        if [[ "$ALLOW_MISSING_TOOLS" == "true" ]]; then
          mark_warn "pip-audit module missing in python env: $PYTHON_BIN"
        else
          mark_fail "pip-audit module missing in python env: $PYTHON_BIN"
        fi
      else
        cat /tmp/pip_audit_gate.log >&2
        mark_fail "pip-audit failed [ai_judge_service]"
      fi
    fi
    rm -f /tmp/pip_audit_gate.log
  fi
fi

{
  echo "# 供应链安全门禁报告"
  echo
  echo "- 生成时间: $(date '+%Y-%m-%d %H:%M:%S %z')"
  echo "- root: $ROOT"
  echo "- allow_missing_tools: $ALLOW_MISSING_TOOLS"
  echo "- cargo_allowlist: $CARGO_ADVISORY_ALLOWLIST"
  echo "- pip_allowlist: $PIP_AUDIT_ALLOWLIST"
  echo "- 结果: $([[ "$FAIL_COUNT" -eq 0 ]] && echo "PASSED" || echo "FAILED")"
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
  echo "## 警告项 ($WARN_COUNT)"
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
  echo "supply chain security gate result: FAILED ($FAIL_COUNT issue(s))"
  exit 1
fi
echo "supply chain security gate result: PASSED"
