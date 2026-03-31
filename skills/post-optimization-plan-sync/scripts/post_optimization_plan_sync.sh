#!/usr/bin/env bash
set -euo pipefail

ROOT=""
PLAN=""
STAGE=""
MODULE=""
SUMMARY=""
STATUS="done"
REASON=""
REWRITE_WHITELIST="8,9"

usage() {
  cat <<'USAGE'
用法:
  post_optimization_plan_sync.sh \
    --stage <阶段标识> \
    --module <optimization-module-name> \
    --summary <summary> \
    [--status <done|in-progress|blocked|todo>] \
    [--plan <plan-file>] \
    [--reason <reason>] \
    [--rewrite-whitelist "8,9"]

说明:
  - 计划文档动态解析优先级:
    1) --plan 显式传入
    2) 环境变量 OPTIMIZATION_PLAN_FILE / CURRENT_PLAN_FILE
    3) 指针文件:
       .codex/current-plan.txt
       .codex/current-plan.md
       docs/dev_plan/.current-plan
    4) git 当前变更中的 docs/dev_plan/*.md
    5) docs/dev_plan 下含“优化执行矩阵 + 下一步优化建议”的最近文档
    6) docs/dev_plan 下最近修改的“计划/重构/优化”文档
    7) 兼容回退: docs/后端代码结构优化计划.md
  - 覆盖更新:
    第 8 节（优化执行矩阵）、第 9 节（下一步优化建议）
  - 追加更新:
    自动识别现有“回写记录”章节；不存在则自动创建。
USAGE
}

resolve_absolute_path() {
  local path="$1"
  if [[ -z "$path" ]]; then
    echo ""
    return
  fi
  if [[ "$path" = /* ]]; then
    echo "$path"
  else
    echo "$ROOT/$path"
  fi
}

file_mtime() {
  local path="$1"
  if stat -f "%m" "$path" >/dev/null 2>&1; then
    stat -f "%m" "$path"
  else
    stat -c "%Y" "$path"
  fi
}

pick_latest_file_from_stdin() {
  local best=""
  local best_mtime="-1"
  local candidate mtime
  while IFS= read -r candidate; do
    [[ -z "$candidate" ]] && continue
    [[ -f "$candidate" ]] || continue
    mtime="$(file_mtime "$candidate" 2>/dev/null || echo 0)"
    [[ -z "$mtime" ]] && mtime=0
    if [[ "$mtime" -gt "$best_mtime" ]]; then
      best="$candidate"
      best_mtime="$mtime"
    fi
  done
  echo "$best"
}

resolve_plan_from_env() {
  local key candidate
  for key in OPTIMIZATION_PLAN_FILE CURRENT_PLAN_FILE; do
    candidate="${!key:-}"
    [[ -n "$candidate" ]] || continue
    candidate="$(resolve_absolute_path "$candidate")"
    if [[ -f "$candidate" ]]; then
      echo "$candidate"
      return
    fi
  done
  echo ""
}

resolve_plan_from_pointer() {
  local pointer candidate
  for pointer in \
    "$ROOT/.codex/current-plan.txt" \
    "$ROOT/.codex/current-plan.md" \
    "$ROOT/docs/dev_plan/.current-plan"; do
    [[ -f "$pointer" ]] || continue
    candidate="$(awk 'NF {print; exit}' "$pointer" 2>/dev/null || true)"
    [[ -n "$candidate" ]] || continue
    candidate="$(resolve_absolute_path "$candidate")"
    if [[ -f "$candidate" ]]; then
      echo "$candidate"
      return
    fi
  done
  echo ""
}

resolve_plan_from_git_changes() {
  local candidate
  if ! git -C "$ROOT" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    echo ""
    return
  fi
  candidate="$(
    {
      git -C "$ROOT" diff --name-only -- 'docs/dev_plan/*.md' 2>/dev/null || true
      git -C "$ROOT" diff --cached --name-only -- 'docs/dev_plan/*.md' 2>/dev/null || true
      git -C "$ROOT" ls-files --others --exclude-standard -- 'docs/dev_plan/*.md' 2>/dev/null || true
    } \
      | awk 'NF' \
      | sort -u \
      | while IFS= read -r rel; do
          resolve_absolute_path "$rel"
        done \
      | pick_latest_file_from_stdin
  )"
  echo "$candidate"
}

resolve_plan_from_structured_match() {
  local candidate
  candidate="$(
    for file in "$ROOT"/docs/dev_plan/*.md; do
      [[ -f "$file" ]] || continue
      if grep -q "优化执行矩阵" "$file" && grep -q "下一步优化建议" "$file"; then
        echo "$file"
      fi
    done | pick_latest_file_from_stdin
  )"
  echo "$candidate"
}

resolve_plan_from_name_match() {
  local candidate
  candidate="$(
    for file in "$ROOT"/docs/dev_plan/*.md; do
      [[ -f "$file" ]] || continue
      case "$(basename "$file")" in
        *计划*.md|*重构*.md|*优化*.md)
          echo "$file"
          ;;
      esac
    done | pick_latest_file_from_stdin
  )"
  echo "$candidate"
}

resolve_plan_from_recent_dev_plan() {
  local candidate
  candidate="$(
    for file in "$ROOT"/docs/dev_plan/*.md; do
      [[ -f "$file" ]] || continue
      echo "$file"
    done | pick_latest_file_from_stdin
  )"
  echo "$candidate"
}

resolve_plan() {
  local candidate
  if [[ -n "$PLAN" ]]; then
    PLAN="$(resolve_absolute_path "$PLAN")"
    return
  fi

  candidate="$(resolve_plan_from_env)"
  if [[ -n "$candidate" ]]; then
    PLAN="$candidate"
    return
  fi

  candidate="$(resolve_plan_from_pointer)"
  if [[ -n "$candidate" ]]; then
    PLAN="$candidate"
    return
  fi

  candidate="$(resolve_plan_from_git_changes)"
  if [[ -n "$candidate" ]]; then
    PLAN="$candidate"
    return
  fi

  candidate="$(resolve_plan_from_structured_match)"
  if [[ -n "$candidate" ]]; then
    PLAN="$candidate"
    return
  fi

  candidate="$(resolve_plan_from_name_match)"
  if [[ -n "$candidate" ]]; then
    PLAN="$candidate"
    return
  fi

  candidate="$(resolve_plan_from_recent_dev_plan)"
  if [[ -n "$candidate" ]]; then
    PLAN="$candidate"
    return
  fi

  candidate="$ROOT/docs/后端代码结构优化计划.md"
  if [[ -f "$candidate" ]]; then
    PLAN="$candidate"
    return
  fi
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --root)
      ROOT="$2"
      shift 2
      ;;
    --plan)
      PLAN="$2"
      shift 2
      ;;
    --stage)
      STAGE="$2"
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
    --status)
      STATUS="$2"
      shift 2
      ;;
    --reason)
      REASON="$2"
      shift 2
      ;;
    --rewrite-whitelist)
      REWRITE_WHITELIST="$2"
      shift 2
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

if [[ -z "$ROOT" ]]; then
  if git rev-parse --show-toplevel >/dev/null 2>&1; then
    ROOT="$(git rev-parse --show-toplevel)"
  else
    ROOT="$(pwd)"
  fi
fi

resolve_plan

if [[ -z "$STAGE" || -z "$MODULE" || -z "$SUMMARY" ]]; then
  echo "缺少必填参数: --stage / --module / --summary" >&2
  usage
  exit 1
fi

if [[ -z "$PLAN" || ! -f "$PLAN" ]]; then
  echo "无法自动定位优化计划文档。请通过 --plan 显式指定。" >&2
  echo "候选文档（docs/dev_plan）："
  ls -1 "$ROOT/docs/dev_plan"/*.md 2>/dev/null || true
  exit 1
fi

normalize_stage() {
  local raw="$1"
  raw="$(echo "$raw" | sed -E 's/^阶段[[:space:]]*//')"
  raw="$(echo "$raw" | tr -d '[:space:]')"
  echo "$raw" | tr '[:lower:]' '[:upper:]'
}

normalize_status() {
  local raw="$1"
  raw="$(echo "$raw" | tr '[:upper:]' '[:lower:]')"
  case "$raw" in
    done|completed|complete|已完成)
      echo "已完成"
      ;;
    in-progress|progress|doing|进行中)
      echo "进行中"
      ;;
    blocked|阻塞)
      echo "阻塞"
      ;;
    todo|pending|not-started|未开始)
      echo "未开始"
      ;;
    *)
      echo ""
      ;;
  esac
}

STAGE="$(normalize_stage "$STAGE")"
STATUS_ZH="$(normalize_status "$STATUS")"

if [[ -z "$STAGE" || ! "$STAGE" =~ ^[A-Z0-9_-]+$ ]]; then
  echo "阶段参数非法，示例: R1 / A / V2-D。" >&2
  exit 1
fi

if [[ -z "$STATUS_ZH" ]]; then
  echo "状态参数非法，支持 done|in-progress|blocked|todo。" >&2
  exit 1
fi

REWRITE_WHITELIST_NORM=""
init_rewrite_whitelist() {
  local normalized part
  normalized="$(echo "$REWRITE_WHITELIST" | tr ';' ',' | tr -d ' ')"
  REWRITE_WHITELIST_NORM=","
  IFS=',' read -r -a parts <<< "$normalized"
  for part in "${parts[@]}"; do
    [[ "$part" =~ ^[0-9]+$ ]] || continue
    REWRITE_WHITELIST_NORM="${REWRITE_WHITELIST_NORM}${part},"
  done
}

allow_rewrite_section() {
  local section_no="$1"
  [[ "$REWRITE_WHITELIST_NORM" == *",${section_no},"* ]]
}

stage_ids=()
stage_titles=()
stage_statuses=()

find_stage_index() {
  local target="$1"
  local i
  for ((i=0; i<${#stage_ids[@]}; i++)); do
    if [[ "${stage_ids[$i]}" == "$target" ]]; then
      echo "$i"
      return
    fi
  done
  echo "-1"
}

ensure_stage_exists() {
  local stage="$1"
  local title="$2"
  local idx
  idx="$(find_stage_index "$stage")"
  if [[ "$idx" -lt 0 ]]; then
    stage_ids+=("$stage")
    stage_titles+=("${title:-待补充标题}")
    stage_statuses+=("未开始")
  fi
}

set_stage_title() {
  local stage="$1"
  local title="$2"
  local idx
  idx="$(find_stage_index "$stage")"
  if [[ "$idx" -lt 0 ]]; then
    stage_ids+=("$stage")
    stage_titles+=("${title:-待补充标题}")
    stage_statuses+=("未开始")
  else
    stage_titles[$idx]="${title:-待补充标题}"
  fi
}

get_stage_title() {
  local stage="$1"
  local idx
  idx="$(find_stage_index "$stage")"
  if [[ "$idx" -lt 0 ]]; then
    echo "待补充标题"
  else
    echo "${stage_titles[$idx]}"
  fi
}

set_stage_status() {
  local stage="$1"
  local status="$2"
  local idx
  idx="$(find_stage_index "$stage")"
  if [[ "$idx" -lt 0 ]]; then
    stage_ids+=("$stage")
    stage_titles+=("待补充标题")
    stage_statuses+=("$status")
  else
    stage_statuses[$idx]="$status"
  fi
}

get_stage_status() {
  local stage="$1"
  local idx
  idx="$(find_stage_index "$stage")"
  if [[ "$idx" -lt 0 ]]; then
    echo "未开始"
  else
    echo "${stage_statuses[$idx]}"
  fi
}

replace_or_append_section() {
  local file="$1"
  local heading="$2"
  local section_file="$3"
  local tmp
  tmp="$(mktemp)"
  awk -v heading="$heading" -v repl="$section_file" '
    BEGIN {
      n = 0
      while ((getline line < repl) > 0) {
        rep[++n] = line
      }
      close(repl)
      in_section = 0
      found = 0
    }
    {
      if ($0 == heading) {
        for (i = 1; i <= n; i++) print rep[i]
        in_section = 1
        found = 1
        next
      }
      if (in_section == 1 && $0 ~ /^## /) {
        in_section = 0
      }
      if (in_section == 0) {
        print $0
      }
    }
    END {
      if (found == 0) {
        print ""
        for (i = 1; i <= n; i++) print rep[i]
      }
    }
  ' "$file" >"$tmp"
  mv "$tmp" "$file"
}

while IFS= read -r line; do
  [[ -z "$line" ]] && continue
  stage_id_raw="$(echo "$line" | sed -E 's/^#{2,4}[[:space:]]*阶段[[:space:]]+([^：:[:space:]]+)[：:].*/\1/')"
  title="$(echo "$line" | sed -E 's/^#{2,4}[[:space:]]*阶段[[:space:]]+[^：:[:space:]]+[：:][[:space:]]*//')"
  if [[ "$stage_id_raw" != "$line" ]]; then
    stage_id="$(normalize_stage "$stage_id_raw")"
  else
    stage_id=""
  fi
  if [[ -n "$stage_id" ]]; then
    set_stage_title "$stage_id" "$title"
  fi
done < <(grep -E "^#{2,4}[[:space:]]*阶段[[:space:]]+[^：:[:space:]]+[：:]" "$PLAN" || true)

if [[ ${#stage_ids[@]} -eq 0 ]]; then
  ensure_stage_exists "$STAGE" "待补充标题"
fi

history_stage=""
while IFS= read -r line; do
  if echo "$line" | grep -Eq '^-?[[:space:]]*阶段:[[:space:]]*'; then
    history_stage="$(echo "$line" | sed -E 's/^-?[[:space:]]*阶段:[[:space:]]*//')"
    continue
  fi
  if [[ -n "$history_stage" ]] && echo "$line" | grep -Eq '^-?[[:space:]]*完成状态:[[:space:]]*'; then
    history_status_raw="$(echo "$line" | sed -E 's/^-?[[:space:]]*完成状态:[[:space:]]*//')"
    history_status="$(normalize_status "$history_status_raw")"
    history_stage_norm="$(normalize_stage "$history_stage")"
    if [[ -n "$history_stage_norm" && -n "$history_status" ]]; then
      set_stage_status "$history_stage_norm" "$history_status"
    fi
    history_stage=""
  fi
done < "$PLAN"

set_stage_status "$STAGE" "$STATUS_ZH"

done_count=0
for s in "${stage_ids[@]}"; do
  if [[ "$(get_stage_status "$s")" == "已完成" ]]; then
    done_count=$((done_count + 1))
  fi
done

next_stage=""
for s in "${stage_ids[@]}"; do
  if [[ "$(get_stage_status "$s")" != "已完成" ]]; then
    next_stage="$s"
    break
  fi
done

next_stage_text="全部阶段已完成，进入上线前稳定性与性能优化。"
if [[ -n "$next_stage" ]]; then
  next_stage_text="阶段 ${next_stage}：$(get_stage_title "$next_stage")"
fi

init_rewrite_whitelist

if allow_rewrite_section "8"; then
  section8_tmp="$(mktemp)"
  sync_ts="$(date '+%Y-%m-%d %H:%M:%S')"
  stage_total="${#stage_ids[@]}"
  {
    echo "## 8. 优化执行矩阵（覆盖更新）"
    echo
    echo "- 同步时间: ${sync_ts}"
    echo "- 本次优化模块: \`${MODULE}\`"
    echo "- 本次回写阶段: \`${STAGE}\`"
    echo "- 阶段完成度: ${done_count}/${stage_total}"
    echo
    echo "### 8.1 阶段状态"
    for s in "${stage_ids[@]}"; do
      checkbox=" "
      current_status="$(get_stage_status "$s")"
      if [[ "$current_status" == "已完成" ]]; then
        checkbox="x"
      fi
      echo "- [${checkbox}] 阶段 ${s} | 状态: ${current_status} | 目标: $(get_stage_title "$s")"
    done
    echo
    echo "### 8.2 判定口径"
    echo "- 已完成：阶段关键交付项已经落地并有测试/验证证据。"
    echo "- 进行中：已开始改动但仍有关键交付项未闭环。"
    echo "- 阻塞：存在外部依赖或关键风险暂未解除。"
    echo "- 未开始：阶段尚未进入实施。"
    echo
    echo "### 8.3 覆盖策略"
    echo "- 本节每次优化模块完成后覆盖更新，避免旧状态残留。"
    echo "- 当前章节重写白名单：\`${REWRITE_WHITELIST}\`。"
  } >"$section8_tmp"
  replace_or_append_section "$PLAN" "## 8. 优化执行矩阵（覆盖更新）" "$section8_tmp"
  rm -f "$section8_tmp"
else
  echo "章节 8 不在重写白名单中，跳过覆盖更新。"
fi

if allow_rewrite_section "9"; then
  section9_tmp="$(mktemp)"
  {
    echo "## 9. 下一步优化建议（覆盖更新）"
    echo
    echo "下一步建议：${next_stage_text}"
    echo
    if [[ -n "$next_stage" ]]; then
      echo "执行动作："
      echo "1. 先聚焦阶段 ${next_stage} 的主交付，避免跨阶段并行导致重构扩散。"
      echo "2. 每完成一个子模块就回写本计划，保持“代码状态 -> 计划状态”一致。"
      echo "3. 若与原计划不一致，必须记录调整原因后再继续。"
    else
      echo "执行动作："
      echo "1. 进入上线前收口：性能压测、故障演练、可观测性补齐。"
      echo "2. 将本计划升级为第二版，按线上问题与业务反馈定义新阶段。"
    fi
  } >"$section9_tmp"
  replace_or_append_section "$PLAN" "## 9. 下一步优化建议（覆盖更新）" "$section9_tmp"
  rm -f "$section9_tmp"
else
  echo "章节 9 不在重写白名单中，跳过覆盖更新。"
fi

section_title="$(grep -E '^## [0-9]+\. .*(回写记录|重构回写记录)' "$PLAN" | head -n1 || true)"
if [[ -z "$section_title" ]]; then
  if grep -q '^## 10\. 优化回写记录（自动）' "$PLAN"; then
    section_title="## 10. 优化回写记录（自动）"
  elif grep -q '^## 14\. 重构回写记录（追加）' "$PLAN"; then
    section_title="## 14. 重构回写记录（追加）"
  else
    section_title="## 10. 优化回写记录（自动）"
  fi
fi

if ! grep -qF "$section_title" "$PLAN"; then
  cat >>"$PLAN" <<'EOF'

---

## 10. 优化回写记录（自动）
EOF
fi

timestamp="$(date '+%Y-%m-%d %H:%M:%S')"
cat >>"$PLAN" <<EOF

### ${timestamp} | ${MODULE}
- 阶段: ${STAGE}
- 完成状态: ${STATUS_ZH}
- 本次摘要: ${SUMMARY}
- 调整原因: ${REASON:-无}
- 下一步建议: ${next_stage_text}
EOF

echo "优化计划同步成功。"
echo "计划文档: $PLAN"
echo "本次阶段: $STAGE"
echo "本次状态: $STATUS_ZH"
echo "下一步建议: $next_stage_text"
