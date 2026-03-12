#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage:
  supply_chain_sbom_attestation.sh [options]

Options:
  --root <path>                      Repo root path (default: git top-level or cwd)
  --report-out <path>                Markdown report output path
                                     default: docs/dev_plan/供应链SBOM与许可证证明报告-<YYYY-MM-DD>.md
  --rust-sbom-out <path>             Rust SBOM JSON output path
                                     default: docs/loadtest/evidence/supply_chain_rust_sbom.json
  --python-sbom-out <path>           Python SBOM JSON output path
                                     default: docs/loadtest/evidence/supply_chain_python_sbom.json
  --license-attestation-out <path>   License attestation env output path
                                     default: docs/loadtest/evidence/supply_chain_license_attestation.env
  --evidence-out <path>              SBOM attestation evidence env output path
                                     default: docs/loadtest/evidence/supply_chain_sbom_attestation.env
  --cargo-deny-bin <path|name>       cargo-deny binary (default: cargo-deny)
  --python-bin <path>                Python binary for package metadata checks
                                     default: ai_judge_service/.venv/bin/python
  --python-requirements <path>       Python requirements file (default: ai_judge_service/requirements.txt)
  --rust-targets <csv>               Rust workspace dirs to snapshot
                                     default: chat,chatapp/src-tauri,swiftide-pgvector
  --allow-missing-tools              Downgrade missing tool checks to warning
  -h, --help                         Show this help
USAGE
}

trim() {
  local value="$1"
  value="${value#${value%%[![:space:]]*}}"
  value="${value%${value##*[![:space:]]}}"
  printf '%s' "$value"
}

json_escape() {
  local value="$1"
  value="${value//\\/\\\\}"
  value="${value//\"/\\\"}"
  value="${value//$'\n'/\\n}"
  value="${value//$'\r'/\\r}"
  value="${value//$'\t'/\\t}"
  printf '%s' "$value"
}

tool_exists() {
  local tool="$1"
  if [[ "$tool" == */* ]]; then
    [[ -x "$tool" ]]
    return
  fi
  command -v "$tool" >/dev/null 2>&1
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

parse_cargo_lock() {
  local lock_file="$1"
  awk '
    function emit_row() {
      if (name != "" && version != "") {
        print name "\t" version "\t" source
      }
    }
    /^\[\[package\]\]/ {
      emit_row()
      in_pkg = 1
      name = ""
      version = ""
      source = ""
      next
    }
    in_pkg && /^name = "/ {
      value = $0
      sub(/^name = "/, "", value)
      sub(/"$/, "", value)
      name = value
      next
    }
    in_pkg && /^version = "/ {
      value = $0
      sub(/^version = "/, "", value)
      sub(/"$/, "", value)
      version = value
      next
    }
    in_pkg && /^source = "/ {
      value = $0
      sub(/^source = "/, "", value)
      sub(/"$/, "", value)
      source = value
      next
    }
    END {
      emit_row()
    }
  ' "$lock_file"
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
RUST_SBOM_OUT=""
PYTHON_SBOM_OUT=""
LICENSE_ATTESTATION_OUT=""
EVIDENCE_OUT=""
CARGO_DENY_BIN="cargo-deny"
PYTHON_BIN=""
PYTHON_REQUIREMENTS=""
RUST_TARGETS_CSV="chat,chatapp/src-tauri,swiftide-pgvector"
ALLOW_MISSING_TOOLS="false"

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
    --rust-sbom-out)
      RUST_SBOM_OUT="$2"
      shift 2
      ;;
    --python-sbom-out)
      PYTHON_SBOM_OUT="$2"
      shift 2
      ;;
    --license-attestation-out)
      LICENSE_ATTESTATION_OUT="$2"
      shift 2
      ;;
    --evidence-out)
      EVIDENCE_OUT="$2"
      shift 2
      ;;
    --cargo-deny-bin)
      CARGO_DENY_BIN="$2"
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
    --rust-targets)
      RUST_TARGETS_CSV="$2"
      shift 2
      ;;
    --allow-missing-tools)
      ALLOW_MISSING_TOOLS="true"
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
  REPORT_OUT="$ROOT/docs/dev_plan/供应链SBOM与许可证证明报告-$(date +%F).md"
fi
if [[ -z "$RUST_SBOM_OUT" ]]; then
  RUST_SBOM_OUT="$ROOT/docs/loadtest/evidence/supply_chain_rust_sbom.json"
fi
if [[ -z "$PYTHON_SBOM_OUT" ]]; then
  PYTHON_SBOM_OUT="$ROOT/docs/loadtest/evidence/supply_chain_python_sbom.json"
fi
if [[ -z "$LICENSE_ATTESTATION_OUT" ]]; then
  LICENSE_ATTESTATION_OUT="$ROOT/docs/loadtest/evidence/supply_chain_license_attestation.env"
fi
if [[ -z "$EVIDENCE_OUT" ]]; then
  EVIDENCE_OUT="$ROOT/docs/loadtest/evidence/supply_chain_sbom_attestation.env"
fi
if [[ -z "$PYTHON_BIN" ]]; then
  PYTHON_BIN="$ROOT/ai_judge_service/.venv/bin/python"
fi
if [[ -z "$PYTHON_REQUIREMENTS" ]]; then
  PYTHON_REQUIREMENTS="$ROOT/ai_judge_service/requirements.txt"
fi

mkdir -p "$(dirname "$REPORT_OUT")"
mkdir -p "$(dirname "$RUST_SBOM_OUT")"
mkdir -p "$(dirname "$PYTHON_SBOM_OUT")"
mkdir -p "$(dirname "$LICENSE_ATTESTATION_OUT")"
mkdir -p "$(dirname "$EVIDENCE_OUT")"

echo "== Supply chain SBOM and license attestation =="
echo "root: $ROOT"
echo "report_out: $REPORT_OUT"
echo "rust_sbom_out: $RUST_SBOM_OUT"
echo "python_sbom_out: $PYTHON_SBOM_OUT"
echo "license_attestation_out: $LICENSE_ATTESTATION_OUT"
echo "evidence_out: $EVIDENCE_OUT"
echo

GENERATED_AT="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
RUST_COMPONENTS_COUNT=0
PYTHON_COMPONENTS_COUNT=0
PYTHON_PINNED_COUNT=0
PYTHON_UNPINNED_COUNT=0
PYTHON_METADATA_KNOWN_LICENSE_COUNT=0
PYTHON_METADATA_UNKNOWN_LICENSE_COUNT=0

RUST_LICENSE_STATUS="pass"
PYTHON_PINNED_STATUS="pass"
PYTHON_METADATA_STATUS="pass"

IFS=',' read -r -a rust_targets <<<"$RUST_TARGETS_CSV"

{
  echo "{"
  echo "  \"generatedAt\": \"$(json_escape "$GENERATED_AT")\","
  echo "  \"format\": \"echoisle-rust-sbom-v1\","
  echo "  \"targets\": ["

  target_first="true"
  for target in "${rust_targets[@]}"; do
    target="$(trim "$target")"
    [[ -z "$target" ]] && continue

    target_dir="$ROOT/$target"
    lock_file="$target_dir/Cargo.lock"
    deny_file="$target_dir/deny.toml"

    if [[ ! -d "$target_dir" ]]; then
      mark_fail "rust target dir missing: $target_dir"
      RUST_LICENSE_STATUS="fail"
      continue
    fi
    if [[ ! -f "$lock_file" ]]; then
      mark_fail "rust Cargo.lock missing: $lock_file"
      RUST_LICENSE_STATUS="fail"
      continue
    fi

    if [[ "$target_first" == "true" ]]; then
      target_first="false"
    else
      echo "    ,"
    fi

    echo "    {"
    echo "      \"target\": \"$(json_escape "$target")\","
    echo "      \"lockFile\": \"$(json_escape "$lock_file")\","
    echo "      \"components\": ["

    component_first="true"
    while IFS=$'\t' read -r pkg_name pkg_version pkg_source; do
      [[ -z "$pkg_name" || -z "$pkg_version" ]] && continue
      if [[ "$component_first" == "true" ]]; then
        component_first="false"
      else
        echo "        ,"
      fi
      echo "        {\"name\": \"$(json_escape "$pkg_name")\", \"version\": \"$(json_escape "$pkg_version")\", \"source\": \"$(json_escape "$pkg_source")\"}"
      RUST_COMPONENTS_COUNT=$((RUST_COMPONENTS_COUNT + 1))
    done < <(parse_cargo_lock "$lock_file")

    echo "      ]"
    echo -n "    }"

    if [[ -f "$deny_file" ]]; then
      if tool_exists "$CARGO_DENY_BIN"; then
        if (cd "$target_dir" && "$CARGO_DENY_BIN" check licenses >/tmp/cargo_deny_licenses.log 2>&1); then
          mark_pass "cargo-deny licenses passed [$target]"
        else
          cat /tmp/cargo_deny_licenses.log >&2 || true
          mark_fail "cargo-deny licenses failed [$target]"
          RUST_LICENSE_STATUS="fail"
        fi
        rm -f /tmp/cargo_deny_licenses.log
      else
        if [[ "$ALLOW_MISSING_TOOLS" == "true" ]]; then
          mark_warn "cargo-deny missing, skip rust license check [$target]"
          if [[ "$RUST_LICENSE_STATUS" != "fail" ]]; then
            RUST_LICENSE_STATUS="warn"
          fi
        else
          mark_fail "cargo-deny missing: $CARGO_DENY_BIN"
          RUST_LICENSE_STATUS="fail"
        fi
      fi
    else
      mark_fail "cargo deny config missing: $deny_file"
      RUST_LICENSE_STATUS="fail"
    fi
  done

  echo
  echo "  ]"
  echo "}"
} >"$RUST_SBOM_OUT"

if [[ "$RUST_COMPONENTS_COUNT" -gt 0 ]]; then
  mark_pass "rust sbom generated (components=$RUST_COMPONENTS_COUNT)"
else
  mark_fail "rust sbom component list is empty"
  RUST_LICENSE_STATUS="fail"
fi

if [[ ! -f "$PYTHON_REQUIREMENTS" ]]; then
  mark_fail "python requirements not found: $PYTHON_REQUIREMENTS"
  PYTHON_PINNED_STATUS="fail"
else
  {
    echo "{"
    echo "  \"generatedAt\": \"$(json_escape "$GENERATED_AT")\","
    echo "  \"format\": \"echoisle-python-sbom-v1\","
    echo "  \"requirementsFile\": \"$(json_escape "$PYTHON_REQUIREMENTS")\","
    echo "  \"components\": ["

    component_first="true"
    while IFS= read -r raw_line || [[ -n "$raw_line" ]]; do
      line="${raw_line%%#*}"
      line="$(trim "$line")"
      [[ -z "$line" ]] && continue
      [[ "$line" == --* ]] && continue
      [[ "$line" == -r* ]] && continue

      name=""
      version=""
      pinned="false"
      if [[ "$line" =~ ^([A-Za-z0-9._-]+)==([^[:space:]]+)$ ]]; then
        name="${BASH_REMATCH[1]}"
        version="${BASH_REMATCH[2]}"
        pinned="true"
        PYTHON_PINNED_COUNT=$((PYTHON_PINNED_COUNT + 1))
      else
        name="$line"
        version=""
        pinned="false"
        PYTHON_UNPINNED_COUNT=$((PYTHON_UNPINNED_COUNT + 1))
      fi

      license_value=""
      if [[ "$pinned" == "true" ]]; then
        if tool_exists "$PYTHON_BIN"; then
          if show_out="$("$PYTHON_BIN" -m pip show "$name" 2>/dev/null)"; then
            license_value="$(printf '%s\n' "$show_out" | awk -F': ' '/^License: / {print $2; exit}')"
          fi
        fi
        if [[ -n "$license_value" && "$license_value" != "UNKNOWN" ]]; then
          PYTHON_METADATA_KNOWN_LICENSE_COUNT=$((PYTHON_METADATA_KNOWN_LICENSE_COUNT + 1))
        else
          PYTHON_METADATA_UNKNOWN_LICENSE_COUNT=$((PYTHON_METADATA_UNKNOWN_LICENSE_COUNT + 1))
        fi
      fi

      if [[ "$component_first" == "true" ]]; then
        component_first="false"
      else
        echo "    ,"
      fi
      echo -n "    {\"name\": \"$(json_escape "$name")\", \"version\": \"$(json_escape "$version")\", \"pinned\": $pinned"
      if [[ "$pinned" == "true" ]]; then
        echo -n ", \"license\": \"$(json_escape "$license_value")\""
      fi
      echo -n "}"
      PYTHON_COMPONENTS_COUNT=$((PYTHON_COMPONENTS_COUNT + 1))
    done <"$PYTHON_REQUIREMENTS"

    echo
    echo "  ]"
    echo "}"
  } >"$PYTHON_SBOM_OUT"
fi

if [[ "$PYTHON_COMPONENTS_COUNT" -gt 0 ]]; then
  mark_pass "python sbom generated (components=$PYTHON_COMPONENTS_COUNT)"
else
  mark_fail "python sbom component list is empty"
  PYTHON_PINNED_STATUS="fail"
fi

if [[ "$PYTHON_UNPINNED_COUNT" -gt 0 ]]; then
  mark_fail "python requirements contain unpinned entries (count=$PYTHON_UNPINNED_COUNT)"
  PYTHON_PINNED_STATUS="fail"
else
  mark_pass "python requirements are fully pinned (count=$PYTHON_PINNED_COUNT)"
fi

if tool_exists "$PYTHON_BIN"; then
  if [[ "$PYTHON_METADATA_UNKNOWN_LICENSE_COUNT" -gt 0 ]]; then
    mark_warn "python license metadata incomplete (unknown=$PYTHON_METADATA_UNKNOWN_LICENSE_COUNT)"
    PYTHON_METADATA_STATUS="warn"
  else
    mark_pass "python license metadata collected (known=$PYTHON_METADATA_KNOWN_LICENSE_COUNT)"
    PYTHON_METADATA_STATUS="pass"
  fi
else
  if [[ "$ALLOW_MISSING_TOOLS" == "true" ]]; then
    mark_warn "python binary missing, skip metadata collection: $PYTHON_BIN"
    PYTHON_METADATA_STATUS="warn"
  else
    mark_fail "python binary missing: $PYTHON_BIN"
    PYTHON_METADATA_STATUS="fail"
  fi
fi

RUST_SBOM_SHA256=""
PYTHON_SBOM_SHA256=""
LICENSE_ATTESTATION_SHA256=""

if RUST_SBOM_SHA256="$(sha256_file "$RUST_SBOM_OUT" 2>/dev/null)"; then
  mark_pass "rust sbom sha256 computed"
else
  mark_fail "failed to compute rust sbom sha256"
fi

if PYTHON_SBOM_SHA256="$(sha256_file "$PYTHON_SBOM_OUT" 2>/dev/null)"; then
  mark_pass "python sbom sha256 computed"
else
  mark_fail "failed to compute python sbom sha256"
fi

{
  echo "LICENSE_GENERATED_AT=$GENERATED_AT"
  echo "LICENSE_CHECK_RUST=$RUST_LICENSE_STATUS"
  echo "LICENSE_CHECK_PYTHON_PINNED=$PYTHON_PINNED_STATUS"
  echo "LICENSE_CHECK_PYTHON_METADATA=$PYTHON_METADATA_STATUS"
  echo "LICENSE_RUST_TARGETS=$RUST_TARGETS_CSV"
  echo "LICENSE_PYTHON_REQUIREMENTS=$PYTHON_REQUIREMENTS"
  echo "LICENSE_PYTHON_KNOWN_COUNT=$PYTHON_METADATA_KNOWN_LICENSE_COUNT"
  echo "LICENSE_PYTHON_UNKNOWN_COUNT=$PYTHON_METADATA_UNKNOWN_LICENSE_COUNT"
} >"$LICENSE_ATTESTATION_OUT"

if LICENSE_ATTESTATION_SHA256="$(sha256_file "$LICENSE_ATTESTATION_OUT" 2>/dev/null)"; then
  mark_pass "license attestation sha256 computed"
else
  mark_fail "failed to compute license attestation sha256"
fi

{
  echo "SBOM_STAGE=preprod"
  echo "SBOM_GENERATED_AT=$GENERATED_AT"
  echo "SBOM_RUST_PATH=$RUST_SBOM_OUT"
  echo "SBOM_PYTHON_PATH=$PYTHON_SBOM_OUT"
  echo "SBOM_LICENSE_ATTESTATION_PATH=$LICENSE_ATTESTATION_OUT"
  echo "SBOM_RUST_SHA256=$RUST_SBOM_SHA256"
  echo "SBOM_PYTHON_SHA256=$PYTHON_SBOM_SHA256"
  echo "SBOM_LICENSE_SHA256=$LICENSE_ATTESTATION_SHA256"
  echo "SBOM_RUST_COMPONENTS_COUNT=$RUST_COMPONENTS_COUNT"
  echo "SBOM_PYTHON_COMPONENTS_COUNT=$PYTHON_COMPONENTS_COUNT"
  echo "SBOM_LICENSE_CHECK_RUST=$RUST_LICENSE_STATUS"
  echo "SBOM_LICENSE_CHECK_PYTHON_PINNED=$PYTHON_PINNED_STATUS"
  echo "SBOM_LICENSE_CHECK_PYTHON_METADATA=$PYTHON_METADATA_STATUS"
} >"$EVIDENCE_OUT"

{
  echo "# 供应链SBOM与许可证证明报告"
  echo
  echo "- 生成时间: $(date '+%Y-%m-%d %H:%M:%S %z')"
  echo "- root: $ROOT"
  echo "- rust_sbom_out: $RUST_SBOM_OUT"
  echo "- python_sbom_out: $PYTHON_SBOM_OUT"
  echo "- license_attestation_out: $LICENSE_ATTESTATION_OUT"
  echo "- evidence_out: $EVIDENCE_OUT"
  echo
  echo "## 核心指标"
  echo "- rust_components: $RUST_COMPONENTS_COUNT"
  echo "- python_components: $PYTHON_COMPONENTS_COUNT"
  echo "- python_pinned: $PYTHON_PINNED_COUNT"
  echo "- python_unpinned: $PYTHON_UNPINNED_COUNT"
  echo "- rust_license_status: $RUST_LICENSE_STATUS"
  echo "- python_pinned_status: $PYTHON_PINNED_STATUS"
  echo "- python_metadata_status: $PYTHON_METADATA_STATUS"
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
if [[ "$FAIL_COUNT" -gt 0 ]]; then
  echo "supply chain sbom attestation result: FAILED ($FAIL_COUNT issue(s))"
  exit 1
fi
echo "supply chain sbom attestation result: PASSED"
