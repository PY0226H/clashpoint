#!/usr/bin/env bash
set -euo pipefail

ROOT=""
TASK_KIND=""
MODULE=""
SUMMARY=""
MODE="auto"
METADATA_OUT=""
DRY_RUN=0

usage() {
  cat <<'USAGE'
用法:
  run_prd_goal_guard.sh \
    --root <repo-root> \
    --task-kind <dev|refactor> \
    --module <module-id> \
    --summary <summary> \
    [--mode <auto|summary|full>] \
    [--metadata-out <path>] \
    [--dry-run]
USAGE
}

trim() {
  local v="$1"
  v="${v#${v%%[![:space:]]*}}"
  v="${v%${v##*[![:space:]]}}"
  printf '%s' "$v"
}

lower_ascii() {
  printf '%s' "$1" | tr '[:upper:]' '[:lower:]'
}

contains_keyword() {
  local haystack="$1"
  local keyword="$2"
  [[ "$haystack" == *"$keyword"* ]]
}

match_first_keyword() {
  local haystack="$1"
  shift
  local keyword
  for keyword in "$@"; do
    if contains_keyword "$haystack" "$keyword"; then
      printf '%s' "$keyword"
      return 0
    fi
  done
  return 1
}

write_metadata() {
  local effective_mode="$1"
  local evidence_paths="$2"
  local reason="$3"
  local summary_doc="$4"
  local authority_prd="$5"

  [[ -z "$METADATA_OUT" ]] && return 0
  mkdir -p "$(dirname "$METADATA_OUT")"
  cat >"$METADATA_OUT" <<EOF_META
effective_mode=$effective_mode
evidence_paths=$evidence_paths
reason=$reason
summary_doc=$summary_doc
authority_prd=$authority_prd
EOF_META
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --root)
      ROOT="$2"
      shift 2
      ;;
    --task-kind)
      TASK_KIND="$2"
      shift 2
      ;;
    --module)
      MODULE="$2"
      shift 2
      ;;
    --summary)
      SUMMARY="$2"
      shift 2
      ;;
    --mode)
      MODE="$2"
      shift 2
      ;;
    --metadata-out)
      METADATA_OUT="$2"
      shift 2
      ;;
    --dry-run)
      DRY_RUN=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "未知参数: $1" >&2
      usage
      exit 1
      ;;
  esac
done

if [[ -z "$ROOT" || -z "$TASK_KIND" || -z "$MODULE" || -z "$SUMMARY" ]]; then
  echo "--root、--task-kind、--module、--summary 为必填参数" >&2
  usage
  exit 1
fi

case "$TASK_KIND" in
  dev|refactor) ;;
  *)
    echo "--task-kind 仅支持 dev|refactor" >&2
    exit 1
    ;;
esac

case "$MODE" in
  auto|summary|full) ;;
  *)
    echo "--mode 仅支持 auto|summary|full" >&2
    exit 1
    ;;
esac

SUMMARY_DOC="$ROOT/docs/harness/product-goals.md"
AUTHORITY_PRD="$ROOT/docs/PRD/在线辩论AI裁判平台完整PRD.md"

if [[ ! -f "$SUMMARY_DOC" ]]; then
  echo "缺少摘要文档: $SUMMARY_DOC" >&2
  exit 1
fi

if [[ ! -f "$AUTHORITY_PRD" ]]; then
  echo "缺少权威 PRD: $AUTHORITY_PRD" >&2
  exit 1
fi

context="$(lower_ascii "$MODULE $SUMMARY")"
effective_mode="summary"
reason="普通模块默认走 product-goals 摘要"
matched_keyword=""

auth_keywords=(auth signin sign-in signup sign-up login password token session sms phone email wechat oauth bind verify permission role access security captcha)
billing_keywords=(wallet payment billing balance ledger recharge topup purchase charge refund receipt)
judge_keywords=(judge ai verdict rubric draw rematch rag report replay voting vote)
ops_keywords=(ops admin release appstore review compliance audit moderation topic schedule)
cross_flow_keywords=(gateway websocket ws kafka redis notification notify cross-service schema migration)

if [[ "$MODE" == "full" ]]; then
  effective_mode="full"
  reason="显式指定 --mode full"
elif [[ "$MODE" == "summary" ]]; then
  effective_mode="summary"
  reason="显式指定 --mode summary"
elif matched_keyword="$(match_first_keyword "$context" "${auth_keywords[@]}")"; then
  effective_mode="full"
  reason="命中高风险认证/权限关键词: $matched_keyword"
elif matched_keyword="$(match_first_keyword "$context" "${billing_keywords[@]}")"; then
  effective_mode="full"
  reason="命中高风险支付/钱包关键词: $matched_keyword"
elif matched_keyword="$(match_first_keyword "$context" "${judge_keywords[@]}")"; then
  effective_mode="full"
  reason="命中高风险 AI 判决关键词: $matched_keyword"
elif matched_keyword="$(match_first_keyword "$context" "${ops_keywords[@]}")"; then
  effective_mode="full"
  reason="命中高风险运营/发布关键词: $matched_keyword"
elif matched_keyword="$(match_first_keyword "$context" "${cross_flow_keywords[@]}")"; then
  effective_mode="full"
  reason="命中跨服务/关键链路关键词: $matched_keyword"
fi

evidence_paths="$SUMMARY_DOC"
if [[ "$effective_mode" == "full" ]]; then
  evidence_paths="$SUMMARY_DOC;$AUTHORITY_PRD"
fi

printf 'summary_doc: %s\n' "$SUMMARY_DOC"
printf 'authority_prd: %s\n' "$AUTHORITY_PRD"
printf 'prd_mode_requested: %s\n' "$MODE"
printf 'prd_mode_effective: %s\n' "$effective_mode"
printf 'full_prd_reason: %s\n' "$reason"
printf 'alignment_check:\n'
printf '1. 本次模块目标是否服务于用户主流程或北极星体验\n'
printf '2. 本次方案是否破坏登录/Lobby/Room/Judge/Wallet/Ops 关键链路\n'
printf '3. 本次范围是否误做当前版本明确不做的能力\n'
printf '4. 若命中高风险范围，是否已回读完整 PRD\n'

if [[ "$DRY_RUN" -eq 0 ]]; then
  sed -n '1,9999p' "$SUMMARY_DOC" >/dev/null
  if [[ "$effective_mode" == "full" ]]; then
    sed -n '1,9999p' "$AUTHORITY_PRD" >/dev/null
  fi
fi

write_metadata "$effective_mode" "$evidence_paths" "$reason" "$SUMMARY_DOC" "$AUTHORITY_PRD"
