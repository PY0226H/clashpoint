#!/usr/bin/env bash
set -euo pipefail

ROOT=""
PLAN_DOC=""
EVIDENCE_DIR=""
DRAFT_SCRIPT=""
RUNTIME_OPS_ENV=""
RUNTIME_OPS_DOC=""
OUTPUT_DOC=""
OUTPUT_ENV=""
EMIT_JSON=""
EMIT_MD=""
RUN_ID=""
STARTED_AT=""
FINISHED_AT=""
STATUS="unknown"

DRAFT_EXIT_CODE=0
DRAFT_STATUS="unknown"
DRAFT_COMPLETED_TOTAL=0
DRAFT_TODO_TOTAL=0
DRAFT_SUMMARY_JSON=""
DRAFT_SUMMARY_MD=""

RUNTIME_OPS_PACK_LINKED="false"
RUNTIME_OPS_PACK_STATUS="unknown"
RELEASE_READINESS_ARTIFACT_STATUS="missing"
RELEASE_READINESS_ARTIFACT_SUMMARY_PATH=""
RELEASE_READINESS_ARTIFACT_REF=""
RELEASE_READINESS_ARTIFACT_MANIFEST_HASH=""
RELEASE_READINESS_ARTIFACT_DECISION=""
RELEASE_READINESS_ARTIFACT_STORAGE_MODE=""

ACTIVE_PLAN_EVIDENCE_STATUS="unknown"
CLOSURE_ARCHIVE_DETECTED="false"
CLOSURE_ARCHIVE_SOURCE="missing"
CLOSURE_ARCHIVE_PATH=""
CLOSURE_ARCHIVE_STATUS="stage_closure_archive_missing"
COMPLETED_DOC=""
TODO_DOC=""
COMPLETED_SECTION_ID=""
COMPLETED_MODULE_COUNT=0
TODO_SECTION_ID=""
TODO_ENV_BLOCKED_DEBT_COUNT=0
LINKED_REAL_ENV_DEBT_ID=""
LONG_TERM_EVIDENCE_STATUS="missing"

usage() {
  cat <<'USAGE'
用法:
  ai_judge_stage_closure_evidence.sh \
    [--root <repo-root>] \
    [--plan-doc <path>] \
    [--evidence-dir <path>] \
    [--draft-script <path>] \
    [--runtime-ops-env <path>] \
    [--runtime-ops-doc <path>] \
    [--output-doc <path>] \
    [--output-env <path>] \
    [--emit-json <path>] \
    [--emit-md <path>]

说明:
  - 生成 AI judge 阶段收口证据摘要：
    1) 执行 stage closure draft 并抽取 completed/todo 候选统计
    2) 检查 runtime ops pack 证据是否已就绪并建立关联
  - 输出状态：
    pass/pending_data/evidence_missing/stage_failed
USAGE
}

iso_now() {
  date -u +"%Y-%m-%dT%H:%M:%SZ"
}

date_cn() {
  date -u +"%Y-%m-%d"
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
  local path="${1:-}"
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

read_env_value() {
  local file="$1"
  local key="$2"
  local line
  line="$(grep -E "^${key}=" "$file" | head -n 1 || true)"
  if [[ -z "$line" ]]; then
    printf '%s' ""
    return
  fi
  printf '%s' "${line#*=}"
}

read_json_number() {
  local file="$1"
  local key="$2"
  local raw
  raw="$(grep -E "\"${key}\"[[:space:]]*:[[:space:]]*[0-9]+" "$file" | head -n 1 || true)"
  if [[ -z "$raw" ]]; then
    printf '0'
    return
  fi
  printf '%s' "$raw" | sed -E "s/.*\"${key}\"[[:space:]]*:[[:space:]]*([0-9]+).*/\\1/"
}

read_json_string() {
  local file="$1"
  local key="$2"
  if [[ ! -f "$file" ]]; then
    printf '%s' ""
    return
  fi
  local compact pattern
  compact="$(tr '\n' ' ' <"$file")"
  pattern="\"${key}\"[[:space:]]*:[[:space:]]*\"([^\"]*)\""
  if [[ "$compact" =~ $pattern ]]; then
    printf '%s' "${BASH_REMATCH[1]}"
    return
  fi
  printf '%s' ""
}

find_release_readiness_artifact_summary() {
  local candidate latest
  for candidate in \
    "$EVIDENCE_DIR/ai_judge_release_readiness_artifact_summary.json" \
    "$EVIDENCE_DIR/release_readiness_artifact_summary.json" \
    "$ROOT/artifacts/harness/ai_judge_release_readiness_artifact_summary.json"; do
    if [[ -f "$candidate" ]]; then
      printf '%s' "$candidate"
      return
    fi
  done
  latest="$(
    find "$EVIDENCE_DIR" "$ROOT/artifacts/harness" -type f \
      \( -iname '*release*readiness*artifact*summary*.json' -o -iname '*release-readiness-artifact*.json' \) \
      2>/dev/null | sort | tail -n 1 || true
  )"
  printf '%s' "$latest"
}

detect_release_readiness_artifact_file() {
  RELEASE_READINESS_ARTIFACT_SUMMARY_PATH="$(find_release_readiness_artifact_summary)"
  RELEASE_READINESS_ARTIFACT_REF=""
  RELEASE_READINESS_ARTIFACT_MANIFEST_HASH=""
  RELEASE_READINESS_ARTIFACT_DECISION=""
  RELEASE_READINESS_ARTIFACT_STORAGE_MODE=""
  if [[ -z "$RELEASE_READINESS_ARTIFACT_SUMMARY_PATH" || ! -f "$RELEASE_READINESS_ARTIFACT_SUMMARY_PATH" ]]; then
    RELEASE_READINESS_ARTIFACT_STATUS="missing"
    return
  fi

  RELEASE_READINESS_ARTIFACT_REF="$(trim "$(read_json_string "$RELEASE_READINESS_ARTIFACT_SUMMARY_PATH" "artifactRef")")"
  RELEASE_READINESS_ARTIFACT_MANIFEST_HASH="$(trim "$(read_json_string "$RELEASE_READINESS_ARTIFACT_SUMMARY_PATH" "manifestHash")")"
  RELEASE_READINESS_ARTIFACT_DECISION="$(trim "$(read_json_string "$RELEASE_READINESS_ARTIFACT_SUMMARY_PATH" "decision")")"
  RELEASE_READINESS_ARTIFACT_STORAGE_MODE="$(trim "$(read_json_string "$RELEASE_READINESS_ARTIFACT_SUMMARY_PATH" "storageMode")")"
  if [[ -n "$RELEASE_READINESS_ARTIFACT_REF" && -n "$RELEASE_READINESS_ARTIFACT_MANIFEST_HASH" ]]; then
    RELEASE_READINESS_ARTIFACT_STATUS="present"
    return
  fi
  RELEASE_READINESS_ARTIFACT_STATUS="invalid"
}

latest_section_id() {
  local file="$1"
  local prefix="$2"
  if [[ ! -f "$file" ]]; then
    printf '%s' ""
    return
  fi
  grep -E "^### ${prefix}[0-9]+\\." "$file" | tail -n 1 | sed -E "s/^### (${prefix}[0-9]+)\\..*/\\1/" || true
}

count_ai_judge_rows_in_section() {
  local file="$1"
  local section_id="$2"
  if [[ ! -f "$file" || -z "$section_id" ]]; then
    printf '0'
    return
  fi
  awk -v section="$section_id" '
    BEGIN { in_section = 0; count = 0 }
    $0 ~ "^### " section "\\." { in_section = 1; next }
    in_section == 1 && /^### / { in_section = 0 }
    in_section == 1 && /^\|[[:space:]]*ai-judge-/ { count += 1 }
    END { print count + 0 }
  ' "$file"
}

count_env_blocked_debts_in_section() {
  local file="$1"
  local section_id="$2"
  if [[ ! -f "$file" || -z "$section_id" ]]; then
    printf '0'
    return
  fi
  awk -v section="$section_id" '
    BEGIN { in_section = 0; count = 0 }
    $0 ~ "^### " section "\\." { in_section = 1; next }
    in_section == 1 && /^### / { in_section = 0 }
    in_section == 1 && /^\|[[:space:]]*ai-judge-/ && ($0 ~ /环境依赖/ || $0 ~ /env_blocked/ || $0 ~ /real-env/) { count += 1 }
    END { print count + 0 }
  ' "$file"
}

find_real_env_debt_in_section() {
  local file="$1"
  local section_id="$2"
  if [[ ! -f "$file" || -z "$section_id" ]]; then
    printf '%s' ""
    return
  fi
  awk -v section="$section_id" '
    BEGIN { in_section = 0 }
    $0 ~ "^### " section "\\." { in_section = 1; next }
    in_section == 1 && /^### / { in_section = 0 }
    in_section == 1 && /^\|[[:space:]]*ai-judge-/ && $0 ~ /real-env-pass-window-execute-on-env/ {
      line = $0
      sub(/^\|[[:space:]]*/, "", line)
      sub(/[[:space:]]*\|.*/, "", line)
      gsub(/`/, "", line)
      gsub(/^[[:space:]]+|[[:space:]]+$/, "", line)
      print line
      exit
    }
  ' "$file"
}

extract_archive_path_from_plan() {
  if [[ ! -f "$PLAN_DOC" ]]; then
    printf '%s' ""
    return
  fi
  grep -Eo '(/[^`[:space:]]+docs/dev_plan/archive/[0-9TZ-]+ai-judge-stage-closure-execute\.md|docs/dev_plan/archive/[0-9TZ-]+ai-judge-stage-closure-execute\.md)' "$PLAN_DOC" | head -n 1 || true
}

detect_latest_archive() {
  local archive_dir="$ROOT/docs/dev_plan/archive"
  if [[ ! -d "$archive_dir" ]]; then
    printf '%s' ""
    return
  fi
  find "$archive_dir" -type f -name '*-ai-judge-stage-closure-execute.md' | sort | tail -n 1 || true
}

parse_args() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --root)
        ROOT="${2:-}"
        shift 2
        ;;
      --plan-doc)
        PLAN_DOC="${2:-}"
        shift 2
        ;;
      --evidence-dir)
        EVIDENCE_DIR="${2:-}"
        shift 2
        ;;
      --draft-script)
        DRAFT_SCRIPT="${2:-}"
        shift 2
        ;;
      --runtime-ops-env)
        RUNTIME_OPS_ENV="${2:-}"
        shift 2
        ;;
      --runtime-ops-doc)
        RUNTIME_OPS_DOC="${2:-}"
        shift 2
        ;;
      --output-doc)
        OUTPUT_DOC="${2:-}"
        shift 2
        ;;
      --output-env)
        OUTPUT_ENV="${2:-}"
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
      -h|--help)
        usage
        exit 0
        ;;
      *)
        echo "未知参数: $1" >&2
        usage
        exit 2
        ;;
    esac
  done
}

run_draft_stage() {
  local run_dir="$1"
  local draft_stdout="$run_dir/stage_closure_draft.stdout.log"

  DRAFT_SUMMARY_JSON="$run_dir/stage_closure_draft.summary.json"
  DRAFT_SUMMARY_MD="$run_dir/stage_closure_draft.summary.md"

  local -a cmd
  cmd=(
    bash "$DRAFT_SCRIPT"
    --root "$ROOT"
    --plan-doc "$PLAN_DOC"
    --emit-json "$DRAFT_SUMMARY_JSON"
    --emit-md "$DRAFT_SUMMARY_MD"
  )

  if "${cmd[@]}" >"$draft_stdout" 2>&1; then
    DRAFT_EXIT_CODE=0
  else
    DRAFT_EXIT_CODE="$?"
  fi

  DRAFT_STATUS="$(grep -E '^ai_judge_stage_closure_draft_status:' "$draft_stdout" | tail -n 1 | awk -F ':' '{print $2}' || true)"
  DRAFT_STATUS="$(trim "$DRAFT_STATUS")"
  if [[ -z "$DRAFT_STATUS" ]]; then
    if [[ "$DRAFT_EXIT_CODE" == "0" ]]; then
      DRAFT_STATUS="pass"
    else
      DRAFT_STATUS="stage_failed"
    fi
  fi

  if [[ -f "$DRAFT_SUMMARY_JSON" ]]; then
    DRAFT_COMPLETED_TOTAL="$(read_json_number "$DRAFT_SUMMARY_JSON" "completed_candidates_total")"
    DRAFT_TODO_TOTAL="$(read_json_number "$DRAFT_SUMMARY_JSON" "todo_candidates_total")"
  else
    DRAFT_COMPLETED_TOTAL=0
    DRAFT_TODO_TOTAL=0
  fi
}

detect_runtime_ops_link() {
  if [[ -f "$RUNTIME_OPS_ENV" && -f "$RUNTIME_OPS_DOC" ]]; then
    RUNTIME_OPS_PACK_LINKED="true"
    RUNTIME_OPS_PACK_STATUS="$(trim "$(read_env_value "$RUNTIME_OPS_ENV" "AI_JUDGE_RUNTIME_OPS_PACK_STATUS")")"
    RELEASE_READINESS_ARTIFACT_STATUS="$(trim "$(read_env_value "$RUNTIME_OPS_ENV" "RELEASE_READINESS_ARTIFACT_STATUS")")"
    RELEASE_READINESS_ARTIFACT_SUMMARY_PATH="$(trim "$(read_env_value "$RUNTIME_OPS_ENV" "RELEASE_READINESS_ARTIFACT_SUMMARY_PATH")")"
    RELEASE_READINESS_ARTIFACT_REF="$(trim "$(read_env_value "$RUNTIME_OPS_ENV" "RELEASE_READINESS_ARTIFACT_REF")")"
    RELEASE_READINESS_ARTIFACT_MANIFEST_HASH="$(trim "$(read_env_value "$RUNTIME_OPS_ENV" "RELEASE_READINESS_ARTIFACT_MANIFEST_HASH")")"
    RELEASE_READINESS_ARTIFACT_DECISION="$(trim "$(read_env_value "$RUNTIME_OPS_ENV" "RELEASE_READINESS_ARTIFACT_DECISION")")"
    RELEASE_READINESS_ARTIFACT_STORAGE_MODE="$(trim "$(read_env_value "$RUNTIME_OPS_ENV" "RELEASE_READINESS_ARTIFACT_STORAGE_MODE")")"
    if [[ -z "$RUNTIME_OPS_PACK_STATUS" ]]; then
      RUNTIME_OPS_PACK_STATUS="unknown"
    fi
    if [[ -z "$RELEASE_READINESS_ARTIFACT_STATUS" ]]; then
      RELEASE_READINESS_ARTIFACT_STATUS="missing"
    fi
  else
    RUNTIME_OPS_PACK_LINKED="false"
    RUNTIME_OPS_PACK_STATUS="unknown"
    detect_release_readiness_artifact_file
  fi
}

detect_backfill_evidence() {
  if [[ "$DRAFT_COMPLETED_TOTAL" != "0" || "$DRAFT_TODO_TOTAL" != "0" ]]; then
    ACTIVE_PLAN_EVIDENCE_STATUS="pass"
  else
    ACTIVE_PLAN_EVIDENCE_STATUS="missing"
  fi

  local archive_candidate
  archive_candidate="$(extract_archive_path_from_plan)"
  if [[ -n "$archive_candidate" ]]; then
    archive_candidate="$(abs_path "$archive_candidate")"
    if [[ -f "$archive_candidate" ]]; then
      CLOSURE_ARCHIVE_DETECTED="true"
      CLOSURE_ARCHIVE_SOURCE="plan_doc"
      CLOSURE_ARCHIVE_PATH="$archive_candidate"
      CLOSURE_ARCHIVE_STATUS="archived"
    fi
  fi
  if [[ "$CLOSURE_ARCHIVE_DETECTED" != "true" ]]; then
    archive_candidate="$(detect_latest_archive)"
    if [[ -n "$archive_candidate" && -f "$archive_candidate" ]]; then
      CLOSURE_ARCHIVE_DETECTED="true"
      CLOSURE_ARCHIVE_SOURCE="latest_archive"
      CLOSURE_ARCHIVE_PATH="$archive_candidate"
      CLOSURE_ARCHIVE_STATUS="archived"
    fi
  fi

  COMPLETED_DOC="$ROOT/docs/dev_plan/completed.md"
  TODO_DOC="$ROOT/docs/dev_plan/todo.md"
  COMPLETED_SECTION_ID="$(latest_section_id "$COMPLETED_DOC" "B")"
  TODO_SECTION_ID="$(latest_section_id "$TODO_DOC" "C")"
  COMPLETED_MODULE_COUNT="$(count_ai_judge_rows_in_section "$COMPLETED_DOC" "$COMPLETED_SECTION_ID")"
  TODO_ENV_BLOCKED_DEBT_COUNT="$(count_env_blocked_debts_in_section "$TODO_DOC" "$TODO_SECTION_ID")"
  LINKED_REAL_ENV_DEBT_ID="$(find_real_env_debt_in_section "$TODO_DOC" "$TODO_SECTION_ID")"

  if [[ "$COMPLETED_MODULE_COUNT" != "0" || "$TODO_ENV_BLOCKED_DEBT_COUNT" != "0" || -n "$LINKED_REAL_ENV_DEBT_ID" ]]; then
    LONG_TERM_EVIDENCE_STATUS="pass"
  else
    LONG_TERM_EVIDENCE_STATUS="missing"
  fi
}

derive_status() {
  if [[ "$DRAFT_EXIT_CODE" != "0" || "$DRAFT_STATUS" != "pass" ]]; then
    STATUS="stage_failed"
    return
  fi

  if [[ "$RUNTIME_OPS_PACK_LINKED" == "true" && ( "$RELEASE_READINESS_ARTIFACT_STATUS" == "missing" || "$RELEASE_READINESS_ARTIFACT_STATUS" == "invalid" ) ]]; then
    STATUS="evidence_missing"
    return
  fi

  if [[ "$ACTIVE_PLAN_EVIDENCE_STATUS" == "pass" ]]; then
    if [[ "$RUNTIME_OPS_PACK_LINKED" != "true" || "$RUNTIME_OPS_PACK_STATUS" == "unknown" ]]; then
      STATUS="pending_data"
      return
    fi
    STATUS="pass"
    return
  fi

  if [[ "$CLOSURE_ARCHIVE_DETECTED" != "true" ]]; then
    STATUS="stage_closure_archive_missing"
    return
  fi

  if [[ "$LONG_TERM_EVIDENCE_STATUS" != "pass" ]]; then
    STATUS="evidence_missing"
    return
  fi

  if [[ "$RUNTIME_OPS_PACK_LINKED" != "true" || "$RUNTIME_OPS_PACK_STATUS" == "unknown" ]]; then
    STATUS="pending_data"
    return
  fi

  if [[ "$CLOSURE_ARCHIVE_DETECTED" == "true" && "$LONG_TERM_EVIDENCE_STATUS" == "pass" ]]; then
    STATUS="pass"
    return
  fi

  STATUS="pass"
}

write_output_env() {
  cat >"$OUTPUT_ENV" <<EOF_ENV
AI_JUDGE_STAGE_CLOSURE_EVIDENCE_STATUS=$STATUS
UPDATED_AT=$FINISHED_AT
RUN_ID=$RUN_ID
PLAN_DOC=$PLAN_DOC
DRAFT_STATUS=$DRAFT_STATUS
DRAFT_EXIT_CODE=$DRAFT_EXIT_CODE
DRAFT_COMPLETED_CANDIDATES=$DRAFT_COMPLETED_TOTAL
DRAFT_TODO_CANDIDATES=$DRAFT_TODO_TOTAL
DRAFT_SUMMARY_JSON=$DRAFT_SUMMARY_JSON
DRAFT_SUMMARY_MD=$DRAFT_SUMMARY_MD
RUNTIME_OPS_PACK_LINKED=$RUNTIME_OPS_PACK_LINKED
RUNTIME_OPS_PACK_STATUS=$RUNTIME_OPS_PACK_STATUS
RUNTIME_OPS_PACK_ENV=$RUNTIME_OPS_ENV
RUNTIME_OPS_PACK_DOC=$RUNTIME_OPS_DOC
RELEASE_READINESS_ARTIFACT_STATUS=$RELEASE_READINESS_ARTIFACT_STATUS
RELEASE_READINESS_ARTIFACT_SUMMARY_PATH=$RELEASE_READINESS_ARTIFACT_SUMMARY_PATH
RELEASE_READINESS_ARTIFACT_REF=$RELEASE_READINESS_ARTIFACT_REF
RELEASE_READINESS_ARTIFACT_MANIFEST_HASH=$RELEASE_READINESS_ARTIFACT_MANIFEST_HASH
RELEASE_READINESS_ARTIFACT_DECISION=$RELEASE_READINESS_ARTIFACT_DECISION
RELEASE_READINESS_ARTIFACT_STORAGE_MODE=$RELEASE_READINESS_ARTIFACT_STORAGE_MODE
ACTIVE_PLAN_EVIDENCE_STATUS=$ACTIVE_PLAN_EVIDENCE_STATUS
CLOSURE_ARCHIVE_DETECTED=$CLOSURE_ARCHIVE_DETECTED
CLOSURE_ARCHIVE_SOURCE=$CLOSURE_ARCHIVE_SOURCE
CLOSURE_ARCHIVE_STATUS=$CLOSURE_ARCHIVE_STATUS
CLOSURE_ARCHIVE_PATH=$CLOSURE_ARCHIVE_PATH
COMPLETED_DOC=$COMPLETED_DOC
COMPLETED_SECTION_ID=$COMPLETED_SECTION_ID
COMPLETED_MODULE_COUNT=$COMPLETED_MODULE_COUNT
TODO_DOC=$TODO_DOC
TODO_SECTION_ID=$TODO_SECTION_ID
TODO_ENV_BLOCKED_DEBT_COUNT=$TODO_ENV_BLOCKED_DEBT_COUNT
LINKED_REAL_ENV_DEBT_ID=$LINKED_REAL_ENV_DEBT_ID
LONG_TERM_EVIDENCE_STATUS=$LONG_TERM_EVIDENCE_STATUS
EOF_ENV
}

write_output_doc() {
  cat >"$OUTPUT_DOC" <<EOF_MD
# AI Judge Stage Closure Evidence 摘要

1. 生成日期：$(date_cn)
2. 运行窗口：$STARTED_AT -> $FINISHED_AT
3. 统一状态：\`$STATUS\`
4. plan_doc：\`$PLAN_DOC\`
5. draft_script：\`$DRAFT_SCRIPT\`

## 收口草案统计

1. draft_status：\`$DRAFT_STATUS\`
2. completed_candidates_total：\`$DRAFT_COMPLETED_TOTAL\`
3. todo_candidates_total：\`$DRAFT_TODO_TOTAL\`
4. draft_summary_json：\`$DRAFT_SUMMARY_JSON\`
5. draft_summary_md：\`$DRAFT_SUMMARY_MD\`

## runtime ops pack 关联

1. runtime_ops_pack_linked：\`$RUNTIME_OPS_PACK_LINKED\`
2. runtime_ops_pack_status：\`$RUNTIME_OPS_PACK_STATUS\`
3. runtime_ops_pack_env：\`$RUNTIME_OPS_ENV\`
4. runtime_ops_pack_doc：\`$RUNTIME_OPS_DOC\`

## release readiness artifact

1. artifact_status：\`$RELEASE_READINESS_ARTIFACT_STATUS\`
2. artifact_ref：\`$RELEASE_READINESS_ARTIFACT_REF\`
3. manifest_hash：\`$RELEASE_READINESS_ARTIFACT_MANIFEST_HASH\`
4. decision：\`$RELEASE_READINESS_ARTIFACT_DECISION\`
5. storage_mode：\`$RELEASE_READINESS_ARTIFACT_STORAGE_MODE\`
6. summary_path：\`$RELEASE_READINESS_ARTIFACT_SUMMARY_PATH\`

## active plan evidence

1. active_plan_evidence_status：\`$ACTIVE_PLAN_EVIDENCE_STATUS\`

## archived closure evidence

1. archive_detected：\`$CLOSURE_ARCHIVE_DETECTED\`
2. archive_source：\`$CLOSURE_ARCHIVE_SOURCE\`
3. archive_status：\`$CLOSURE_ARCHIVE_STATUS\`
4. archive_path：\`$CLOSURE_ARCHIVE_PATH\`

## long-term completed/todo evidence

1. completed_section：\`$COMPLETED_SECTION_ID\`
2. completed_module_count：\`$COMPLETED_MODULE_COUNT\`
3. todo_section：\`$TODO_SECTION_ID\`
4. todo_env_blocked_debt_count：\`$TODO_ENV_BLOCKED_DEBT_COUNT\`
5. linked_real_env_debt_id：\`$LINKED_REAL_ENV_DEBT_ID\`
6. long_term_evidence_status：\`$LONG_TERM_EVIDENCE_STATUS\`

## 输出工件

1. stage closure env：\`$OUTPUT_ENV\`
2. stage closure doc：\`$OUTPUT_DOC\`
3. summary json：\`$EMIT_JSON\`
4. summary md：\`$EMIT_MD\`
EOF_MD
}

write_json_summary() {
  cat >"$EMIT_JSON" <<EOF_JSON
{
  "module": "ai-judge-stage-closure-evidence",
  "status": "$(json_escape "$STATUS")",
  "run_id": "$(json_escape "$RUN_ID")",
  "started_at": "$(json_escape "$STARTED_AT")",
  "finished_at": "$(json_escape "$FINISHED_AT")",
  "plan_doc": "$(json_escape "$PLAN_DOC")",
  "draft": {
    "status": "$(json_escape "$DRAFT_STATUS")",
    "exit_code": $DRAFT_EXIT_CODE,
    "completed_candidates_total": $DRAFT_COMPLETED_TOTAL,
    "todo_candidates_total": $DRAFT_TODO_TOTAL,
    "summary_json": "$(json_escape "$DRAFT_SUMMARY_JSON")",
    "summary_md": "$(json_escape "$DRAFT_SUMMARY_MD")"
  },
  "runtime_ops_pack": {
    "linked": $([[ "$RUNTIME_OPS_PACK_LINKED" == "true" ]] && echo "true" || echo "false"),
    "status": "$(json_escape "$RUNTIME_OPS_PACK_STATUS")",
    "env": "$(json_escape "$RUNTIME_OPS_ENV")",
    "doc": "$(json_escape "$RUNTIME_OPS_DOC")",
    "release_readiness_artifact": {
      "status": "$(json_escape "$RELEASE_READINESS_ARTIFACT_STATUS")",
      "summary_path": "$(json_escape "$RELEASE_READINESS_ARTIFACT_SUMMARY_PATH")",
      "artifact_ref": "$(json_escape "$RELEASE_READINESS_ARTIFACT_REF")",
      "manifest_hash": "$(json_escape "$RELEASE_READINESS_ARTIFACT_MANIFEST_HASH")",
      "decision": "$(json_escape "$RELEASE_READINESS_ARTIFACT_DECISION")",
      "storage_mode": "$(json_escape "$RELEASE_READINESS_ARTIFACT_STORAGE_MODE")"
    }
  },
  "closure_backfill": {
    "active_plan_evidence_status": "$(json_escape "$ACTIVE_PLAN_EVIDENCE_STATUS")",
    "archive_detected": $([[ "$CLOSURE_ARCHIVE_DETECTED" == "true" ]] && echo "true" || echo "false"),
    "archive_source": "$(json_escape "$CLOSURE_ARCHIVE_SOURCE")",
    "archive_status": "$(json_escape "$CLOSURE_ARCHIVE_STATUS")",
    "archive_path": "$(json_escape "$CLOSURE_ARCHIVE_PATH")",
    "completed_doc": "$(json_escape "$COMPLETED_DOC")",
    "completed_section": "$(json_escape "$COMPLETED_SECTION_ID")",
    "completed_module_count": $COMPLETED_MODULE_COUNT,
    "todo_doc": "$(json_escape "$TODO_DOC")",
    "todo_section": "$(json_escape "$TODO_SECTION_ID")",
    "todo_env_blocked_debt_count": $TODO_ENV_BLOCKED_DEBT_COUNT,
    "linked_real_env_debt_id": "$(json_escape "$LINKED_REAL_ENV_DEBT_ID")",
    "long_term_evidence_status": "$(json_escape "$LONG_TERM_EVIDENCE_STATUS")"
  },
  "outputs": {
    "output_env": "$(json_escape "$OUTPUT_ENV")",
    "output_doc": "$(json_escape "$OUTPUT_DOC")",
    "summary_json": "$(json_escape "$EMIT_JSON")",
    "summary_md": "$(json_escape "$EMIT_MD")"
  }
}
EOF_JSON
}

write_md_summary() {
  cat >"$EMIT_MD" <<EOF_MD
# ai-judge-stage-closure-evidence

- status: \`$STATUS\`
- run_id: \`$RUN_ID\`
- started_at: \`$STARTED_AT\`
- finished_at: \`$FINISHED_AT\`
- plan_doc: \`$PLAN_DOC\`

## draft

1. status: \`$DRAFT_STATUS\`
2. completed_candidates_total: \`$DRAFT_COMPLETED_TOTAL\`
3. todo_candidates_total: \`$DRAFT_TODO_TOTAL\`
4. summary_json: \`$DRAFT_SUMMARY_JSON\`
5. summary_md: \`$DRAFT_SUMMARY_MD\`

## runtime_ops_pack

1. linked: \`$RUNTIME_OPS_PACK_LINKED\`
2. status: \`$RUNTIME_OPS_PACK_STATUS\`
3. env: \`$RUNTIME_OPS_ENV\`
4. doc: \`$RUNTIME_OPS_DOC\`

## release_readiness_artifact

1. status: \`$RELEASE_READINESS_ARTIFACT_STATUS\`
2. artifact_ref: \`$RELEASE_READINESS_ARTIFACT_REF\`
3. manifest_hash: \`$RELEASE_READINESS_ARTIFACT_MANIFEST_HASH\`
4. decision: \`$RELEASE_READINESS_ARTIFACT_DECISION\`
5. storage_mode: \`$RELEASE_READINESS_ARTIFACT_STORAGE_MODE\`
6. summary_path: \`$RELEASE_READINESS_ARTIFACT_SUMMARY_PATH\`

## closure_backfill

1. active_plan_evidence_status: \`$ACTIVE_PLAN_EVIDENCE_STATUS\`
2. archive_detected: \`$CLOSURE_ARCHIVE_DETECTED\`
3. archive_source: \`$CLOSURE_ARCHIVE_SOURCE\`
4. archive_status: \`$CLOSURE_ARCHIVE_STATUS\`
5. archive_path: \`$CLOSURE_ARCHIVE_PATH\`
6. completed_section: \`$COMPLETED_SECTION_ID\`
7. completed_module_count: \`$COMPLETED_MODULE_COUNT\`
8. todo_section: \`$TODO_SECTION_ID\`
9. todo_env_blocked_debt_count: \`$TODO_ENV_BLOCKED_DEBT_COUNT\`
10. linked_real_env_debt_id: \`$LINKED_REAL_ENV_DEBT_ID\`
11. long_term_evidence_status: \`$LONG_TERM_EVIDENCE_STATUS\`
EOF_MD
}

main() {
  parse_args "$@"
  resolve_root

  if [[ -z "$PLAN_DOC" ]]; then
    PLAN_DOC="$ROOT/docs/dev_plan/当前开发计划.md"
  else
    PLAN_DOC="$(abs_path "$PLAN_DOC")"
  fi
  if [[ -z "$EVIDENCE_DIR" ]]; then
    EVIDENCE_DIR="$ROOT/docs/loadtest/evidence"
  else
    EVIDENCE_DIR="$(abs_path "$EVIDENCE_DIR")"
  fi
  if [[ -z "$DRAFT_SCRIPT" ]]; then
    DRAFT_SCRIPT="$ROOT/scripts/harness/ai_judge_stage_closure_draft.sh"
  else
    DRAFT_SCRIPT="$(abs_path "$DRAFT_SCRIPT")"
  fi
  if [[ -z "$RUNTIME_OPS_ENV" ]]; then
    RUNTIME_OPS_ENV="$EVIDENCE_DIR/ai_judge_runtime_ops_pack.env"
  else
    RUNTIME_OPS_ENV="$(abs_path "$RUNTIME_OPS_ENV")"
  fi
  if [[ -z "$RUNTIME_OPS_DOC" ]]; then
    RUNTIME_OPS_DOC="$EVIDENCE_DIR/ai_judge_runtime_ops_pack.md"
  else
    RUNTIME_OPS_DOC="$(abs_path "$RUNTIME_OPS_DOC")"
  fi
  if [[ -z "$OUTPUT_DOC" ]]; then
    OUTPUT_DOC="$EVIDENCE_DIR/ai_judge_stage_closure_evidence.md"
  else
    OUTPUT_DOC="$(abs_path "$OUTPUT_DOC")"
  fi
  if [[ -z "$OUTPUT_ENV" ]]; then
    OUTPUT_ENV="$EVIDENCE_DIR/ai_judge_stage_closure_evidence.env"
  else
    OUTPUT_ENV="$(abs_path "$OUTPUT_ENV")"
  fi

  RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-ai-judge-stage-closure-evidence"
  STARTED_AT="$(iso_now)"

  if [[ -z "$EMIT_JSON" ]]; then
    EMIT_JSON="$ROOT/artifacts/harness/${RUN_ID}.summary.json"
  else
    EMIT_JSON="$(abs_path "$EMIT_JSON")"
  fi
  if [[ -z "$EMIT_MD" ]]; then
    EMIT_MD="$ROOT/artifacts/harness/${RUN_ID}.summary.md"
  else
    EMIT_MD="$(abs_path "$EMIT_MD")"
  fi

  local run_dir
  run_dir="$ROOT/artifacts/harness/$RUN_ID"
  mkdir -p "$run_dir"
  ensure_parent_dir "$OUTPUT_DOC"
  ensure_parent_dir "$OUTPUT_ENV"
  ensure_parent_dir "$EMIT_JSON"
  ensure_parent_dir "$EMIT_MD"

  if [[ ! -f "$PLAN_DOC" ]]; then
    echo "计划文档不存在: $PLAN_DOC" >&2
    exit 1
  fi
  if [[ ! -x "$DRAFT_SCRIPT" ]]; then
    echo "stage closure draft 脚本不可执行: $DRAFT_SCRIPT" >&2
    exit 1
  fi

  run_draft_stage "$run_dir"
  detect_runtime_ops_link
  detect_backfill_evidence
  derive_status

  FINISHED_AT="$(iso_now)"
  write_output_env
  write_output_doc
  write_json_summary
  write_md_summary

  echo "ai_judge_stage_closure_evidence_status: $STATUS"
  echo "draft_status: $DRAFT_STATUS (exit=$DRAFT_EXIT_CODE)"
  echo "draft_completed_candidates: $DRAFT_COMPLETED_TOTAL"
  echo "draft_todo_candidates: $DRAFT_TODO_TOTAL"
  echo "runtime_ops_pack_linked: $RUNTIME_OPS_PACK_LINKED"
  echo "runtime_ops_pack_status: $RUNTIME_OPS_PACK_STATUS"
  echo "release_readiness_artifact_status: $RELEASE_READINESS_ARTIFACT_STATUS"
  echo "release_readiness_artifact_ref: $RELEASE_READINESS_ARTIFACT_REF"
  echo "release_readiness_manifest_hash: $RELEASE_READINESS_ARTIFACT_MANIFEST_HASH"
  echo "active_plan_evidence_status: $ACTIVE_PLAN_EVIDENCE_STATUS"
  echo "closure_backfill_archive_detected: $CLOSURE_ARCHIVE_DETECTED"
  echo "closure_backfill_archive_source: $CLOSURE_ARCHIVE_SOURCE"
  echo "closure_backfill_archive_status: $CLOSURE_ARCHIVE_STATUS"
  echo "closure_backfill_archive_path: $CLOSURE_ARCHIVE_PATH"
  echo "closure_backfill_completed_section: $COMPLETED_SECTION_ID"
  echo "closure_backfill_completed_module_count: $COMPLETED_MODULE_COUNT"
  echo "closure_backfill_todo_section: $TODO_SECTION_ID"
  echo "closure_backfill_todo_env_blocked_debt_count: $TODO_ENV_BLOCKED_DEBT_COUNT"
  echo "closure_backfill_linked_real_env_debt_id: $LINKED_REAL_ENV_DEBT_ID"
  echo "output_env: $OUTPUT_ENV"
  echo "output_doc: $OUTPUT_DOC"
  echo "summary_json: $EMIT_JSON"
  echo "summary_md: $EMIT_MD"
}

main "$@"
