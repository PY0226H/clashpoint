#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage:
  supply_chain_allowlist_expiry_check.sh [options]

Options:
  --root <path>                   Repo root path (default: git top-level or cwd)
  --report-out <path>             Markdown report output path
                                  default: docs/dev_plan/供应链allowlist到期巡检报告-<YYYY-MM-DD>.md
  --warning-days <days>           Warn when expires within N days (default: 7)
  --fail-on-warning               Treat warning items as failure
  --cargo-advisory-allowlist <path>
                                  default: scripts/release/security_allowlists/cargo_deny_advisories_allowlist.csv
  --pip-audit-allowlist <path>
                                  default: scripts/release/security_allowlists/pip_audit_vulns_allowlist.csv
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
WARN_ITEMS=()
FAIL_ITEMS=()
PASS_COUNT=0
WARN_COUNT=0
FAIL_COUNT=0

mark_pass() {
  PASS_ITEMS+=("$1")
  PASS_COUNT=$((PASS_COUNT + 1))
}

mark_warn() {
  WARN_ITEMS+=("$1")
  WARN_COUNT=$((WARN_COUNT + 1))
}

mark_fail() {
  FAIL_ITEMS+=("$1")
  FAIL_COUNT=$((FAIL_COUNT + 1))
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

record_expiry_status() {
  local kind="$1"
  local row_ref="$2"
  local id_value="$3"
  local scope_value="$4"
  local expires_on="$5"

  local epoch
  epoch="$(date_to_epoch "$expires_on" 2>/dev/null || true)"
  if [[ -z "$epoch" ]]; then
    mark_fail "$kind allowlist expires_on invalid [$row_ref id=$id_value scope=$scope_value]"
    return
  fi

  local end_of_day=$((epoch + 86399))
  local seconds_left=$((end_of_day - NOW_EPOCH))
  local days_left=$((seconds_left / 86400))

  if [[ "$seconds_left" -lt 0 ]]; then
    mark_fail "$kind allowlist expired [$id_value scope=$scope_value expires_on=$expires_on]"
    return
  fi

  if [[ "$days_left" -le "$WARNING_DAYS" ]]; then
    mark_warn "$kind allowlist expiring_soon [$id_value scope=$scope_value expires_on=$expires_on days_left=$days_left]"
    return
  fi

  mark_pass "$kind allowlist active [$id_value scope=$scope_value expires_on=$expires_on days_left=$days_left]"
}

check_cargo_allowlist() {
  local file="$1"
  if [[ ! -f "$file" ]]; then
    mark_fail "cargo allowlist missing: $file"
    return
  fi

  local row_count=0
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

    row_count=$((row_count + 1))
    local row_ref="$file:$line_no"

    if [[ -n "$extra" ]]; then
      mark_fail "cargo allowlist row has too many fields [$row_ref]"
      continue
    fi
    if [[ ! "$advisory_id" =~ ^RUSTSEC-[0-9]{4}-[0-9]{4}$ ]]; then
      mark_fail "cargo allowlist advisory_id invalid [$row_ref]"
      continue
    fi
    if [[ -z "$target" || -z "$owner" || -z "$reason" ]]; then
      mark_fail "cargo allowlist target/owner/reason missing [$row_ref]"
      continue
    fi

    record_expiry_status "cargo" "$row_ref" "$advisory_id" "$target" "$expires_on"
  done <"$file"

  if [[ "$row_count" -eq 0 ]]; then
    mark_warn "cargo allowlist empty: $file"
  fi
}

check_pip_allowlist() {
  local file="$1"
  if [[ ! -f "$file" ]]; then
    mark_fail "pip allowlist missing: $file"
    return
  fi

  local row_count=0
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

    row_count=$((row_count + 1))
    local row_ref="$file:$line_no"

    if [[ -n "$extra" ]]; then
      mark_fail "pip allowlist row has too many fields [$row_ref]"
      continue
    fi
    if [[ ! "$vuln_id" =~ ^(GHSA|PYSEC|CVE)- ]]; then
      mark_fail "pip allowlist vuln_id invalid [$row_ref]"
      continue
    fi
    if [[ -z "$package" || -z "$owner" || -z "$reason" ]]; then
      mark_fail "pip allowlist package/owner/reason missing [$row_ref]"
      continue
    fi

    record_expiry_status "pip" "$row_ref" "$vuln_id" "$package" "$expires_on"
  done <"$file"

  if [[ "$row_count" -eq 0 ]]; then
    mark_warn "pip allowlist empty: $file"
  fi
}

ROOT=""
REPORT_OUT=""
WARNING_DAYS="7"
FAIL_ON_WARNING="false"
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
    --warning-days)
      WARNING_DAYS="$2"
      shift 2
      ;;
    --fail-on-warning)
      FAIL_ON_WARNING="true"
      shift
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

if [[ -z "$REPORT_OUT" ]]; then
  REPORT_OUT="$ROOT/docs/dev_plan/供应链allowlist到期巡检报告-$(date +%F).md"
fi
if [[ -z "$CARGO_ADVISORY_ALLOWLIST" ]]; then
  CARGO_ADVISORY_ALLOWLIST="$ROOT/scripts/release/security_allowlists/cargo_deny_advisories_allowlist.csv"
fi
if [[ -z "$PIP_AUDIT_ALLOWLIST" ]]; then
  PIP_AUDIT_ALLOWLIST="$ROOT/scripts/release/security_allowlists/pip_audit_vulns_allowlist.csv"
fi

if [[ ! "$WARNING_DAYS" =~ ^[0-9]+$ ]]; then
  echo "warning-days must be a non-negative integer" >&2
  exit 1
fi

NOW_EPOCH="$(date +%s)"

mkdir -p "$(dirname "$REPORT_OUT")"

echo "== Supply chain allowlist expiry check =="
echo "root: $ROOT"
echo "report_out: $REPORT_OUT"
echo "warning_days: $WARNING_DAYS"
echo "fail_on_warning: $FAIL_ON_WARNING"
echo

check_cargo_allowlist "$CARGO_ADVISORY_ALLOWLIST"
check_pip_allowlist "$PIP_AUDIT_ALLOWLIST"

effective_fail_count="$FAIL_COUNT"
if [[ "$FAIL_ON_WARNING" == "true" && "$WARN_COUNT" -gt 0 ]]; then
  effective_fail_count=$((effective_fail_count + WARN_COUNT))
fi

{
  echo "# 供应链 Allowlist 到期巡检报告"
  echo
  echo "- 生成时间: $(date '+%Y-%m-%d %H:%M:%S %z')"
  echo "- root: $ROOT"
  echo "- warning_days: $WARNING_DAYS"
  echo "- fail_on_warning: $FAIL_ON_WARNING"
  echo "- cargo_allowlist: $CARGO_ADVISORY_ALLOWLIST"
  echo "- pip_allowlist: $PIP_AUDIT_ALLOWLIST"
  echo "- 结果: $([[ "$effective_fail_count" -eq 0 ]] && echo "PASSED" || echo "FAILED")"
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
if [[ "$effective_fail_count" -gt 0 ]]; then
  echo "allowlist expiry check result: FAILED (fail=$FAIL_COUNT warn=$WARN_COUNT mode_fail_on_warning=$FAIL_ON_WARNING)"
  exit 1
fi
echo "allowlist expiry check result: PASSED"
