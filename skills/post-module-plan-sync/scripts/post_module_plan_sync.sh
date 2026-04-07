#!/usr/bin/env bash
set -euo pipefail

ROOT=""
PLAN=""
SLOT=""
MODULE=""
SUMMARY=""
PRIORITY="P1"
STATUS="进行中"
NOTE=""
NEXT_STEPS=""
HISTORY_DATE=""
MATRIX_HEADING="### 已完成/未完成矩阵"
NEXT_HEADING="### 下一开发模块建议"
HISTORY_HEADING="### 模块完成同步历史"
DRY_RUN=0

usage() {
  cat <<'USAGE'
用法:
  post_module_plan_sync.sh \
    --module <module-name> \
    --summary <summary> \
    [--priority <P0|P1|P2|...>] \
    [--status <status-text>] \
    [--note <matrix-note>] \
    [--next-steps "建议1;建议2;建议3"] \
    [--plan <plan-doc-path>] \
    [--slot <slot-name>] \
    [--history-date <YYYY-MM-DD>] \
    [--matrix-heading "### 已完成/未完成矩阵"] \
    [--next-heading "### 下一开发模块建议"] \
    [--history-heading "### 模块完成同步历史"] \
    [--root <repo-root>] \
    [--dry-run]

说明:
  - 不写死计划文档路径，默认优先按活动计划入口与命名 slot 解析。
  - 自动识别顺序:
    1) --plan
    2) --slot
    3) POST_MODULE_ACTIVE_PLAN / ACTIVE_PLAN_DOC / PLAN_DOC
    4) POST_MODULE_PLAN_SLOT / ACTIVE_PLAN_SLOT / PLAN_SLOT
    5) .codex/plan-slots/*.txt
    6) legacy fallback: git status 中匹配 *开发计划*.md 的改动文件
    7) legacy fallback: docs/dev_plan/*开发计划*.md 最近修改文件
    8) legacy fallback: docs/**/*开发计划*.md 最近修改文件
USAGE
}

trim() {
  local v="$1"
  v="${v#${v%%[![:space:]]*}}"
  v="${v%${v##*[![:space:]]}}"
  printf '%s' "$v"
}

mtime_of() {
  local file="$1"
  if stat -f %m "$file" >/dev/null 2>&1; then
    stat -f %m "$file"
  else
    stat -c %Y "$file"
  fi
}

resolve_path() {
  local root="$1"
  local path="$2"
  if [[ "$path" = /* ]]; then
    printf '%s' "$path"
  else
    printf '%s/%s' "$root" "$path"
  fi
}

normalize_slot() {
  local slot="$1"
  slot="$(trim "$slot")"
  if [[ -z "$slot" ]]; then
    echo ""
    return
  fi
  if [[ ! "$slot" =~ ^[A-Za-z0-9._-]+$ ]]; then
    echo "非法 slot 名称: $slot" >&2
    exit 1
  fi
  printf '%s' "$slot"
}

slot_pointer_path() {
  local root="$1"
  local slot="$2"
  printf '%s/.codex/plan-slots/%s.txt' "$root" "$slot"
}

read_pointer_target() {
  local root="$1"
  local pointer="$2"
  local raw=""
  [[ -f "$pointer" ]] || return 1
  raw="$(awk 'NF {print; exit}' "$pointer" 2>/dev/null || true)"
  [[ -n "$raw" ]] || return 1
  resolve_path "$root" "$raw"
}

resolve_plan_from_slot() {
  local slot="$1"
  local pointer target
  slot="$(normalize_slot "$slot")"
  pointer="$(slot_pointer_path "$ROOT" "$slot")"
  if [[ ! -f "$pointer" ]]; then
    echo "未找到 slot 指针文件: $pointer" >&2
    exit 1
  fi
  target="$(read_pointer_target "$ROOT" "$pointer" || true)"
  if [[ -z "$target" ]]; then
    echo "slot 指针为空或无效: $pointer" >&2
    exit 1
  fi
  if [[ ! -f "$target" ]]; then
    echo "slot 指向的计划文档不存在: $target" >&2
    exit 1
  fi
  printf '%s' "$target"
}

collect_active_slots() {
  local pointer slot target
  for pointer in "$ROOT"/.codex/plan-slots/*.txt; do
    [[ -f "$pointer" ]] || continue
    slot="$(basename "$pointer" .txt)"
    target="$(read_pointer_target "$ROOT" "$pointer" || true)"
    [[ -n "$target" && -f "$target" ]] || continue
    printf '%s\t%s\n' "$slot" "$target"
  done
}

resolve_plan_from_slots() {
  local active default_target count only_target
  active="$(collect_active_slots)"
  count="$(printf '%s\n' "$active" | awk 'NF' | wc -l | tr -d ' ')"

  if [[ "$count" -gt 1 ]]; then
    echo "检测到多个活动计划 slot，请显式传入 --slot 或 --plan。" >&2
    printf '%s\n' "$active" | awk -F '\t' 'NF >= 2 { printf "  - %s => %s\n", $1, $2 }' >&2
    exit 1
  fi

  default_target="$(read_pointer_target "$ROOT" "$(slot_pointer_path "$ROOT" "default")" || true)"
  if [[ -n "$default_target" && -f "$default_target" && "$count" -le 1 ]]; then
    printf '%s' "$default_target"
    return 0
  fi

  if [[ "$count" -eq 1 ]]; then
    only_target="$(printf '%s\n' "$active" | awk -F '\t' 'NF >= 2 { print $2; exit }')"
    if [[ -n "$only_target" && -f "$only_target" ]]; then
      printf '%s' "$only_target"
      return 0
    fi
  fi

  return 1
}

pick_latest_existing_file() {
  local candidates="$1"
  local best=""
  local best_mtime="-1"
  local f m
  while IFS= read -r f; do
    [[ -z "$f" ]] && continue
    [[ -f "$f" ]] || continue
    m="$(mtime_of "$f" 2>/dev/null || echo 0)"
    if [[ -z "$best" || "$m" -gt "$best_mtime" ]]; then
      best="$f"
      best_mtime="$m"
    fi
  done <<< "$candidates"
  printf '%s' "$best"
}

replace_section_block() {
  local file="$1"
  local heading="$2"
  local block_file="$3"
  local tmp
  tmp="$(mktemp)"
  awk -v heading="$heading" -v repl="$block_file" '
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
      if (in_section == 1 && ($0 ~ /^### / || $0 ~ /^## /)) {
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

upsert_matrix_row() {
  local file="$1"
  local heading="$2"
  local module="$3"
  local row="$4"
  local tmp
  tmp="$(mktemp)"

  awk -v heading="$heading" -v module="$module" -v row="$row" '
    function trim(s) {
      gsub(/^[[:space:]]+|[[:space:]]+$/, "", s)
      return s
    }
    BEGIN {
      in_section = 0
      found_heading = 0
      table_seen = 0
      row_written = 0
    }
    {
      if ($0 == heading) {
        print $0
        in_section = 1
        found_heading = 1
        next
      }

      if (in_section == 1) {
        if ($0 ~ /^### / || $0 ~ /^## /) {
          if (row_written == 0) {
            if (table_seen == 0) {
              print ""
              print "| 模块 | 优先级 | 状态 | 说明 |"
              print "|---|---|---|---|"
            }
            print row
            row_written = 1
          }
          in_section = 0
          print $0
          next
        }

        if ($0 ~ /^\|/) {
          table_seen = 1
          split($0, cols, "|")
          key = ""
          if (length(cols) >= 2) {
            key = trim(cols[2])
          }
          if (key == module) {
            print row
            row_written = 1
          } else {
            print $0
          }
          next
        }

        if (table_seen == 1 && row_written == 0) {
          print row
          row_written = 1
        }
        print $0
        next
      }

      print $0
    }
    END {
      if (in_section == 1 && row_written == 0) {
        if (table_seen == 0) {
          print ""
          print "| 模块 | 优先级 | 状态 | 说明 |"
          print "|---|---|---|---|"
        }
        print row
      }

      if (found_heading == 0) {
        print ""
        print heading
        print ""
        print "| 模块 | 优先级 | 状态 | 说明 |"
        print "|---|---|---|---|"
        print row
      }
    }
  ' "$file" >"$tmp"

  mv "$tmp" "$file"
}

append_history_line() {
  local file="$1"
  local heading="$2"
  local line="$3"

  if grep -Fqx -- "$line" "$file"; then
    return 0
  fi

  local tmp
  tmp="$(mktemp)"

  awk -v heading="$heading" -v line="$line" '
    BEGIN {
      in_section = 0
      found = 0
      inserted = 0
    }
    {
      if ($0 == heading) {
        found = 1
        in_section = 1
        print $0
        next
      }

      if (in_section == 1 && ($0 ~ /^### / || $0 ~ /^## /)) {
        if (inserted == 0) {
          print line
          inserted = 1
        }
        in_section = 0
        print $0
        next
      }

      print $0
    }
    END {
      if (found == 1 && inserted == 0) {
        print line
      }
      if (found == 0) {
        print ""
        print heading
        print ""
        print line
      }
    }
  ' "$file" >"$tmp"

  mv "$tmp" "$file"
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
    --slot)
      SLOT="$2"
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
    --priority)
      PRIORITY="$2"
      shift 2
      ;;
    --status)
      STATUS="$2"
      shift 2
      ;;
    --note)
      NOTE="$2"
      shift 2
      ;;
    --next-steps)
      NEXT_STEPS="$2"
      shift 2
      ;;
    --history-date)
      HISTORY_DATE="$2"
      shift 2
      ;;
    --matrix-heading)
      MATRIX_HEADING="$2"
      shift 2
      ;;
    --next-heading)
      NEXT_HEADING="$2"
      shift 2
      ;;
    --history-heading)
      HISTORY_HEADING="$2"
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

if [[ -z "$MODULE" || -z "$SUMMARY" ]]; then
  echo "缺少必填参数: --module / --summary" >&2
  usage
  exit 1
fi

if [[ -z "$ROOT" ]]; then
  if git rev-parse --show-toplevel >/dev/null 2>&1; then
    ROOT="$(git rev-parse --show-toplevel)"
  else
    ROOT="$(pwd)"
  fi
fi

if [[ -z "$HISTORY_DATE" ]]; then
  HISTORY_DATE="$(date '+%Y-%m-%d')"
fi

if [[ -z "$NOTE" ]]; then
  NOTE="$SUMMARY"
fi

if [[ -n "$PLAN" ]]; then
  PLAN="$(resolve_path "$ROOT" "$PLAN")"
  if [[ ! -f "$PLAN" ]]; then
    echo "计划文档不存在: $PLAN" >&2
    exit 1
  fi
else
  candidates=""
  slot_from_env=""

  if [[ -z "$SLOT" ]]; then
    for env_name in POST_MODULE_PLAN_SLOT ACTIVE_PLAN_SLOT PLAN_SLOT; do
      eval "env_value=\${$env_name:-}"
      if [[ -n "${env_value:-}" ]]; then
        slot_from_env="$env_value"
        break
      fi
    done
  fi

  if [[ -n "$SLOT" || -n "$slot_from_env" ]]; then
    PLAN="$(resolve_plan_from_slot "${SLOT:-$slot_from_env}")"
  else
    for env_name in POST_MODULE_ACTIVE_PLAN ACTIVE_PLAN_DOC PLAN_DOC; do
      eval "env_value=\${$env_name:-}"
      if [[ -n "${env_value:-}" ]]; then
        candidates+="$(resolve_path "$ROOT" "$env_value")"$'\n'
      fi
    done

    PLAN="$(pick_latest_existing_file "$candidates")"
    if [[ -z "$PLAN" ]]; then
      PLAN="$(resolve_plan_from_slots || true)"
    fi
  fi

  if [[ -z "$PLAN" ]]; then
    candidates=""

    if git -C "$ROOT" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
      while IFS= read -r rel; do
        rel="$(trim "$rel")"
        [[ -z "$rel" ]] && continue
        if [[ "$rel" == *.md && "$rel" == *开发计划* ]]; then
          candidates+="$(resolve_path "$ROOT" "$rel")"$'\n'
        fi
      done < <(git -C "$ROOT" status --porcelain 2>/dev/null | awk '{print $NF}')
    fi

    while IFS= read -r f; do
      [[ -z "$f" ]] && continue
      candidates+="$f"$'\n'
    done < <(find "$ROOT/docs/dev_plan" -type f -name "*开发计划*.md" 2>/dev/null || true)

    while IFS= read -r f; do
      [[ -z "$f" ]] && continue
      candidates+="$f"$'\n'
    done < <(find "$ROOT/docs" -type f -name "*开发计划*.md" 2>/dev/null || true)

    PLAN="$(pick_latest_existing_file "$candidates")"

    if [[ -z "$PLAN" ]]; then
      echo "无法自动识别当前开发计划文档，请通过 --plan 或 --slot 显式指定。" >&2
      exit 1
    fi
  fi
fi

if [[ "$DRY_RUN" -eq 1 ]]; then
  printf 'dry-run: 目标计划文档 = %s\n' "$PLAN"
  if [[ -n "$SLOT" ]]; then
    printf 'dry-run: slot = %s\n' "$SLOT"
  fi
  printf 'dry-run: 模块 = %s\n' "$MODULE"
  printf 'dry-run: 状态 = %s\n' "$STATUS"
  exit 0
fi

safe_note="${NOTE//|/／}"
row="| ${MODULE} | ${PRIORITY} | ${STATUS} | ${safe_note} |"

upsert_matrix_row "$PLAN" "$MATRIX_HEADING" "$MODULE" "$row"

if [[ -n "$(trim "$NEXT_STEPS")" ]]; then
  block_file="$(mktemp)"
  {
    echo "$NEXT_HEADING"
    echo ""
    idx=1
    IFS=';' read -r -a items <<< "$NEXT_STEPS"
    for item in "${items[@]}"; do
      item="$(trim "$item")"
      [[ -z "$item" ]] && continue
      printf '%d. %s\n' "$idx" "$item"
      idx=$((idx + 1))
    done
    if [[ "$idx" -eq 1 ]]; then
      echo "1. （待补充下一步开发建议）"
    fi
  } >"$block_file"
  replace_section_block "$PLAN" "$NEXT_HEADING" "$block_file"
  rm -f "$block_file"
fi

history_line="- ${HISTORY_DATE}：推进 \`${MODULE}\`；${SUMMARY}"
append_history_line "$PLAN" "$HISTORY_HEADING" "$history_line"

printf '计划同步完成:\n- 文档: %s\n- 矩阵: 已更新模块 `%s`\n' "$PLAN" "$MODULE"
if [[ -n "$(trim "$NEXT_STEPS")" ]]; then
  printf -- '- 下一开发模块建议: 已更新\n'
else
  printf -- '- 下一开发模块建议: 本次未改写（未提供 --next-steps）\n'
fi
printf -- '- 历史: 已追加 `%s`\n' "$HISTORY_DATE"
