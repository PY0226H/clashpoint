#!/usr/bin/env bash
set -euo pipefail

ROOT=""
PROFILE=""
EMIT_JSON=""
EMIT_MD=""
COLLECT_LOGS=0
COLLECT_METRICS=0
COLLECT_TRACE=0
RUN_ID=""
STARTED_AT=""
FINISHED_AT=""
CHECKS_FILE=""
COLLECTORS_FILE=""
OVERALL_STATUS="pass"
CHECK_TOTAL=0
COLLECTOR_TOTAL=0
MISSING_TOTAL=0
FAIL_TOTAL=0

usage() {
  cat <<'USAGE'
用法:
  journey_verify.sh \
    --profile <auth|lobby|room|judge-ops|release> \
    [--emit-json <path>] \
    [--emit-md <path>] \
    [--collect-logs] \
    [--collect-metrics] \
    [--collect-trace] \
    [--root <repo-root>]

说明:
  - 当前阶段（P3-1）先统一 runtime verify 入口、profile 分发与摘要格式。
  - 具体业务旅程细化将在后续 P3-2 / P3-3 / P3-4 中继续落地。
  - 若缺少可直接消费的运行态证据，结果会显式标记为 evidence_missing。
USAGE
}

trim() {
  local value="${1:-}"
  value="${value#${value%%[![:space:]]*}}"
  value="${value%${value##*[![:space:]]}}"
  printf '%s' "$value"
}

json_escape() {
  local value="${1:-}"
  value="${value//\\/\\\\}"
  value="${value//\"/\\\"}"
  value="${value//$'\n'/\\n}"
  value="${value//$'\r'/\\r}"
  value="${value//$'\t'/\\t}"
  printf '%s' "$value"
}

iso_now() {
  date -u +"%Y-%m-%dT%H:%M:%SZ"
}

sanitize_id() {
  local value="$1"
  value="$(printf '%s' "$value" | tr '[:upper:]' '[:lower:]')"
  value="$(printf '%s' "$value" | sed -E 's/[^a-z0-9._-]+/-/g; s/^-+//; s/-+$//')"
  [[ -z "$value" ]] && value="journey"
  printf '%s' "$value"
}

resolve_root() {
  if [[ -n "$ROOT" ]]; then
    return
  fi
  if git rev-parse --show-toplevel >/dev/null 2>&1; then
    ROOT="$(git rev-parse --show-toplevel)"
  else
    ROOT="$(pwd)"
  fi
}

abs_path() {
  local path="$1"
  if [[ -z "$path" ]]; then
    printf '%s' ""
  elif [[ "$path" = /* ]]; then
    printf '%s' "$path"
  else
    printf '%s' "$ROOT/$path"
  fi
}

ensure_parent_dir() {
  local path="$1"
  mkdir -p "$(dirname "$path")"
}

evidence_to_json_array() {
  local raw="${1:-}"
  local first=1
  local item
  printf '['
  while IFS= read -r item || [[ -n "$item" ]]; do
    item="$(trim "$item")"
    [[ -z "$item" ]] && continue
    printf '%s"%s"' "$([[ "$first" -eq 1 ]] && echo "" || echo ",")" "$(json_escape "$item")"
    first=0
  done < <(printf '%s' "$raw" | tr ';' '\n')
  printf ']'
}

count_semicolon_items() {
  local raw="${1:-}"
  local item
  local count=0
  while IFS= read -r item || [[ -n "$item" ]]; do
    item="$(trim "$item")"
    [[ -z "$item" ]] && continue
    count=$((count + 1))
  done < <(printf '%s' "$raw" | tr ';' '\n')
  printf '%s' "$count"
}

collect_latest_ai_judge_evidence() {
  local limit="${1:-6}"
  local root_dir="$ROOT/artifacts/harness"
  local evidence=""
  local picked=0
  local file
  local -a candidates=()
  local -a sorted=()

  [[ -d "$root_dir" ]] || {
    printf '%s' ""
    return
  }

  while IFS= read -r file; do
    [[ -f "$file" ]] || continue
    candidates+=("$file")
  done < <(
    find "$root_dir" -maxdepth 1 -type f \
      \( -name "*ai-judge-*.summary.json" -o -name "*ai-judge-*.summary.md" \) \
      -print 2>/dev/null
  )

  [[ "${#candidates[@]}" -gt 0 ]] || {
    printf '%s' ""
    return
  }

  while IFS= read -r file; do
    [[ -f "$file" ]] || continue
    sorted+=("$file")
  done < <(ls -1t "${candidates[@]}" 2>/dev/null || true)

  for file in "${sorted[@]}"; do
    evidence="${evidence:+${evidence};}${file}"
    picked=$((picked + 1))
    if [[ "$picked" -ge "$limit" ]]; then
      break
    fi
  done

  printf '%s' "$evidence"
}

profile_known() {
  case "$1" in
    auth|lobby|room|judge-ops|release) return 0 ;;
    *) return 1 ;;
  esac
}

profile_phase() {
  case "$1" in
    auth) printf '%s' "P3-2" ;;
    lobby|room) printf '%s' "P3-3" ;;
    judge-ops|release) printf '%s' "P3-4" ;;
  esac
}

profile_goal() {
  case "$1" in
    auth) printf '%s' "认证链路统一运行态验证" ;;
    lobby) printf '%s' "大厅 topics/sessions/join 基础旅程验证" ;;
    room) printf '%s' "房间 messages/ws/replay/ack 基础旅程验证" ;;
    judge-ops) printf '%s' "裁判与运维读写链路验证" ;;
    release) printf '%s' "发布前门禁与供应链脚本聚合验证" ;;
  esac
}

register_status() {
  local status="$1"
  case "$status" in
    fail)
      OVERALL_STATUS="fail"
      FAIL_TOTAL=$((FAIL_TOTAL + 1))
      ;;
    env_blocked)
      if [[ "$OVERALL_STATUS" != "fail" ]]; then
        OVERALL_STATUS="env_blocked"
      fi
      ;;
    evidence_missing)
      if [[ "$OVERALL_STATUS" == "pass" ]]; then
        OVERALL_STATUS="evidence_missing"
      fi
      MISSING_TOTAL=$((MISSING_TOTAL + 1))
      ;;
    *) ;;
  esac
}

append_check() {
  local check_id="$1"
  local title="$2"
  local status="$3"
  local note="$4"
  local source_refs="$5"
  local command_hint="$6"
  local evidence_paths="${7:-}"
  printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
    "$check_id" "$title" "$status" "$note" "$source_refs" "$command_hint" "$evidence_paths" >>"$CHECKS_FILE"
  CHECK_TOTAL=$((CHECK_TOTAL + 1))
  register_status "$status"
}

append_collector() {
  local collector_id="$1"
  local requested="$2"
  local status="$3"
  local note="$4"
  local evidence_paths="${5:-}"
  printf '%s\t%s\t%s\t%s\t%s\n' \
    "$collector_id" "$requested" "$status" "$note" "$evidence_paths" >>"$COLLECTORS_FILE"
  COLLECTOR_TOTAL=$((COLLECTOR_TOTAL + 1))
  register_status "$status"
}

init_run() {
  local ts profile_id
  ts="$(date -u +%Y%m%dT%H%M%SZ)"
  profile_id="$(sanitize_id "$PROFILE")"
  RUN_ID="${ts}-${profile_id}"
  STARTED_AT="$(iso_now)"
  CHECKS_FILE="$(mktemp)"
  COLLECTORS_FILE="$(mktemp)"

  if [[ -z "$EMIT_JSON" ]]; then
    EMIT_JSON="$ROOT/artifacts/harness/${RUN_ID}.journey.json"
  else
    EMIT_JSON="$(abs_path "$EMIT_JSON")"
  fi
  if [[ -z "$EMIT_MD" ]]; then
    EMIT_MD="$ROOT/artifacts/harness/${RUN_ID}.journey.md"
  else
    EMIT_MD="$(abs_path "$EMIT_MD")"
  fi

  ensure_parent_dir "$EMIT_JSON"
  ensure_parent_dir "$EMIT_MD"
}

build_collector_records() {
  if [[ "$COLLECT_LOGS" -eq 1 ]]; then
    append_collector \
      "logs" \
      "true" \
      "evidence_missing" \
      "P3-1 仅建立统一入口，日志采集器将在后续 profile 落地时补齐。" \
      ""
  else
    append_collector "logs" "false" "skipped" "未请求日志采集。" ""
  fi

  if [[ "$COLLECT_METRICS" -eq 1 ]]; then
    append_collector \
      "metrics" \
      "true" \
      "evidence_missing" \
      "P3-1 仅建立统一入口，指标采集器将在后续 profile 落地时补齐。" \
      ""
  else
    append_collector "metrics" "false" "skipped" "未请求指标采集。" ""
  fi

  if [[ "$COLLECT_TRACE" -eq 1 ]]; then
    append_collector \
      "trace" \
      "true" \
      "evidence_missing" \
      "P3-1 仅建立统一入口，trace 采集器将在后续 profile 落地时补齐。" \
      ""
  else
    append_collector "trace" "false" "skipped" "未请求 trace 采集。" ""
  fi
}

build_profile_checks() {
  append_check \
    "profile-dispatch" \
    "profile 分发与统一摘要" \
    "pass" \
    "已进入 ${PROFILE} profile，并按统一 JSON/Markdown 格式产出结果。" \
    "$ROOT/scripts/harness/journey_verify.sh;$ROOT/docs/harness/30-runtime-verify.md" \
    ""

  case "$PROFILE" in
    auth)
      append_check \
        "auth-web-journey" \
        "认证 smoke（web）" \
        "evidence_missing" \
        "auth profile 已注册，但具体认证旅程将在 P3-2 中固化。当前先暴露可复用脚本与证据缺口。" \
        "$ROOT/frontend/package.json;$ROOT/frontend/tests/e2e/auth-smoke.spec.ts;$ROOT/docs/learning/Restful_Api/008_post_api_auth_v2_sms_send.md;$ROOT/docs/learning/Restful_Api/009_post_api_auth_v2_signup_phone.md" \
        "cd $ROOT/frontend && pnpm e2e:auth:web"
      append_check \
        "auth-desktop-journey" \
        "认证 smoke（desktop）" \
        "evidence_missing" \
        "desktop 认证链路将在 P3-2 中与 web 版本一起固化，当前仅给出统一入口与推荐命令。" \
        "$ROOT/frontend/package.json;$ROOT/frontend/tests/e2e/auth-smoke.spec.ts" \
        "cd $ROOT/frontend && pnpm e2e:auth:desktop"
      ;;
    lobby)
      append_check \
        "lobby-web-journey" \
        "大厅 topics / sessions / join" \
        "evidence_missing" \
        "lobby profile 已注册，但具体旅程步骤将在 P3-3 中固化。" \
        "$ROOT/frontend/tests/e2e/auth-smoke.spec.ts;$ROOT/docs/learning/Restful_Api/019_get_api_debate_topics.md" \
        "cd $ROOT/frontend && TARGET_APP=web playwright test --config ./playwright.config.ts --grep \"@smoke lobby\""
      ;;
    room)
      append_check \
        "room-web-journey" \
        "房间 judge-draw / pin-message / wallet" \
        "evidence_missing" \
        "room profile 已注册，但消息、ws/replay/ack 的统一验证将在 P3-3 中继续实现。" \
        "$ROOT/frontend/tests/e2e/auth-smoke.spec.ts" \
        "cd $ROOT/frontend && TARGET_APP=web playwright test --config ./playwright.config.ts --grep \"@smoke room\""
      ;;
    judge-ops)
      local judge_ops_evidence
      local judge_ops_status
      local judge_ops_note
      local judge_ops_count
      judge_ops_evidence="$(collect_latest_ai_judge_evidence 6)"
      if [[ -n "$judge_ops_evidence" ]]; then
        judge_ops_count="$(count_semicolon_items "$judge_ops_evidence")"
        judge_ops_status="pass"
        judge_ops_note="已扫描到 ${judge_ops_count} 份 ai_judge 模块门禁摘要，可作为 judge-ops 当前运行态证据。"
      else
        judge_ops_status="evidence_missing"
        judge_ops_note="judge-ops 已接入 ai_judge 证据扫描，但当前未找到模块门禁摘要；请先运行 ai_judge 模块测试门禁。"
      fi
      append_check \
        "judge-ops-ai-judge-evidence" \
        "裁判与运维证据扫描（ai_judge）" \
        "$judge_ops_status" \
        "$judge_ops_note" \
        "$ROOT/artifacts/harness;$ROOT/scripts/harness/ai_judge_evidence_closure.sh;$ROOT/skills/post-module-test-guard/scripts/run_test_gate.sh;$ROOT/ai_judge_service/tests" \
        "bash $ROOT/scripts/harness/ai_judge_evidence_closure.sh" \
        "$judge_ops_evidence"
      ;;
    release)
      append_check \
        "release-preflight" \
        "发布前预检聚合" \
        "evidence_missing" \
        "release profile 已注册，但聚合执行与结果归因将在 P3-4 中接入统一入口。" \
        "$ROOT/scripts/release/appstore_preflight_check.sh;$ROOT/scripts/release/v2d_stage_acceptance_gate.sh;$ROOT/scripts/release/ai_judge_m7_stage_acceptance_gate.sh" \
        "bash $ROOT/scripts/release/appstore_preflight_check.sh"
      append_check \
        "release-supply-chain" \
        "供应链与发布安全门禁" \
        "evidence_missing" \
        "供应链脚本已存在，但 P3-1 只建立 runtime verify 入口，不改变这些脚本的既有语义。" \
        "$ROOT/scripts/release/supply_chain_security_gate.sh;$ROOT/scripts/release/supply_chain_allowlist_expiry_check.sh;$ROOT/scripts/release/supply_chain_preprod_chaos_drill.sh;$ROOT/scripts/release/supply_chain_sbom_attestation.sh" \
        "bash $ROOT/scripts/release/supply_chain_security_gate.sh"
      ;;
  esac
}

write_json() {
  FINISHED_AT="$(iso_now)"
  {
    printf '{\n'
    printf '  "run_id": "%s",\n' "$(json_escape "$RUN_ID")"
    printf '  "root": "%s",\n' "$(json_escape "$ROOT")"
    printf '  "profile": "%s",\n' "$(json_escape "$PROFILE")"
    printf '  "phase_owner": "%s",\n' "$(json_escape "$(profile_phase "$PROFILE")")"
    printf '  "goal": "%s",\n' "$(json_escape "$(profile_goal "$PROFILE")")"
    printf '  "status": "%s",\n' "$(json_escape "$OVERALL_STATUS")"
    printf '  "started_at": "%s",\n' "$(json_escape "$STARTED_AT")"
    printf '  "finished_at": "%s",\n' "$(json_escape "$FINISHED_AT")"
    printf '  "outputs": {\n'
    printf '    "json": "%s",\n' "$(json_escape "$EMIT_JSON")"
    printf '    "markdown": "%s"\n' "$(json_escape "$EMIT_MD")"
    printf '  },\n'
    printf '  "collect_requests": {\n'
    printf '    "logs": %s,\n' "$([[ "$COLLECT_LOGS" -eq 1 ]] && echo true || echo false)"
    printf '    "metrics": %s,\n' "$([[ "$COLLECT_METRICS" -eq 1 ]] && echo true || echo false)"
    printf '    "trace": %s\n' "$([[ "$COLLECT_TRACE" -eq 1 ]] && echo true || echo false)"
    printf '  },\n'
    printf '  "counts": {\n'
    printf '    "checks_total": %s,\n' "$CHECK_TOTAL"
    printf '    "collectors_total": %s,\n' "$COLLECTOR_TOTAL"
    printf '    "evidence_missing_total": %s,\n' "$MISSING_TOTAL"
    printf '    "fail_total": %s\n' "$FAIL_TOTAL"
    printf '  },\n'
    printf '  "collectors": [\n'
    local first=1
    local collector_id requested status note evidence_paths
    while IFS=$'\t' read -r collector_id requested status note evidence_paths; do
      [[ -z "${collector_id:-}" ]] && continue
      printf '    %s{"collector_id":"%s","requested":%s,"status":"%s","note":"%s","evidence_paths":%s}\n' \
        "$([[ "$first" -eq 1 ]] && echo "" || echo ",")" \
        "$(json_escape "$collector_id")" \
        "$requested" \
        "$(json_escape "$status")" \
        "$(json_escape "$note")" \
        "$(evidence_to_json_array "$evidence_paths")"
      first=0
    done <"$COLLECTORS_FILE"
    printf '  ],\n'
    printf '  "checks": [\n'
    first=1
    local check_id title source_refs command_hint
    while IFS=$'\t' read -r check_id title status note source_refs command_hint evidence_paths; do
      [[ -z "${check_id:-}" ]] && continue
      printf '    %s{"check_id":"%s","title":"%s","status":"%s","note":"%s","source_refs":%s,"command_hint":"%s","evidence_paths":%s}\n' \
        "$([[ "$first" -eq 1 ]] && echo "" || echo ",")" \
        "$(json_escape "$check_id")" \
        "$(json_escape "$title")" \
        "$(json_escape "$status")" \
        "$(json_escape "$note")" \
        "$(evidence_to_json_array "$source_refs")" \
        "$(json_escape "$command_hint")" \
        "$(evidence_to_json_array "$evidence_paths")"
      first=0
    done <"$CHECKS_FILE"
    printf '  ]\n'
    printf '}\n'
  } >"$EMIT_JSON"
}

write_markdown() {
  {
    printf '# Journey Verify Summary\n\n'
    printf -- '- run_id: `%s`\n' "$RUN_ID"
    printf -- '- profile: `%s`\n' "$PROFILE"
    printf -- '- phase_owner: `%s`\n' "$(profile_phase "$PROFILE")"
    printf -- '- goal: %s\n' "$(profile_goal "$PROFILE")"
    printf -- '- status: `%s`\n' "$OVERALL_STATUS"
    printf -- '- started_at: `%s`\n' "$STARTED_AT"
    printf -- '- finished_at: `%s`\n' "$FINISHED_AT"
    printf -- '- output_json: `%s`\n' "$EMIT_JSON"
    printf -- '- output_md: `%s`\n' "$EMIT_MD"
    printf '\n## Collectors\n\n'
    printf '| Collector | Requested | Status | Note |\n'
    printf '|---|---|---|---|\n'
    local collector_id requested status note evidence_paths
    while IFS=$'\t' read -r collector_id requested status note evidence_paths; do
      [[ -z "${collector_id:-}" ]] && continue
      printf '| %s | %s | %s | %s |\n' "$collector_id" "$requested" "$status" "$note"
    done <"$COLLECTORS_FILE"
    printf '\n## Checks\n\n'
    printf '| Check | Status | Command Hint | Note |\n'
    printf '|---|---|---|---|\n'
    local check_id title source_refs command_hint
    while IFS=$'\t' read -r check_id title status note source_refs command_hint evidence_paths; do
      [[ -z "${check_id:-}" ]] && continue
      printf '| %s | %s | %s | %s |\n' "$title" "$status" "${command_hint:-（无）}" "$note"
    done <"$CHECKS_FILE"
    printf '\n## Source Refs\n\n'
    while IFS=$'\t' read -r check_id title status note source_refs command_hint evidence_paths; do
      [[ -z "${check_id:-}" ]] && continue
      printf '### %s\n\n' "$title"
      if [[ -n "$source_refs" ]]; then
        printf '%s\n' "$source_refs" | tr ';' '\n' | sed 's/^/- /'
      else
        printf -- '- （无）\n'
      fi
      printf '\n'
    done <"$CHECKS_FILE"
  } >"$EMIT_MD"
}

cleanup() {
  rm -f "${CHECKS_FILE:-}" "${COLLECTORS_FILE:-}"
}

trap cleanup EXIT

while [[ $# -gt 0 ]]; do
  case "$1" in
    --profile)
      PROFILE="${2:-}"
      shift 2
      ;;
    --emit-json)
      EMIT_JSON="${2:-}"
      shift 2
      ;;
    --emit-md)
      EMIT_MD="${2:-}"
      shift 2
      ;;
    --collect-logs)
      COLLECT_LOGS=1
      shift
      ;;
    --collect-metrics)
      COLLECT_METRICS=1
      shift
      ;;
    --collect-trace)
      COLLECT_TRACE=1
      shift
      ;;
    --root)
      ROOT="${2:-}"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "未知参数: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if [[ -z "$PROFILE" ]]; then
  echo "--profile 为必填参数" >&2
  usage >&2
  exit 2
fi

if ! profile_known "$PROFILE"; then
  echo "不支持的 profile: $PROFILE" >&2
  echo "允许值: auth | lobby | room | judge-ops | release" >&2
  exit 2
fi

resolve_root
ROOT="$(abs_path "$ROOT")"
init_run
build_collector_records
build_profile_checks
write_json
write_markdown

printf 'journey_verify_status: %s\n' "$OVERALL_STATUS"
printf 'journey_verify_profile: %s\n' "$PROFILE"
printf 'journey_verify_json: %s\n' "$EMIT_JSON"
printf 'journey_verify_md: %s\n' "$EMIT_MD"
