#!/usr/bin/env bash
set -euo pipefail

ROOT=""
PLAN_DOC=""
MAPPING_DOC=""
EMIT_JSON=""
EMIT_MD=""
RUN_ID=""
STARTED_AT=""
FINISHED_AT=""
STATUS="pass"

START_MARK="<!-- AI_JUDGE_NEXT_PLAN_BOOTSTRAP:START -->"
END_MARK="<!-- AI_JUDGE_NEXT_PLAN_BOOTSTRAP:END -->"

usage() {
  cat <<'USAGE'
用法:
  ai_judge_next_plan_bootstrap.sh \
    [--root <repo-root>] \
    [--plan-doc <path>] \
    [--mapping-doc <path>] \
    [--emit-json <path>] \
    [--emit-md <path>]

说明:
  - 将当前开发计划从“阶段收口后轻量态”升级为“下一阶段可执行蓝图”。
  - 以幂等方式写入 bootstrap 蓝图块（重复执行只会替换，不会重复追加）。
USAGE
}

iso_now() {
  date -u +"%Y-%m-%dT%H:%M:%SZ"
}

date_cn() {
  date -u +"%Y-%m-%d"
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
      --mapping-doc)
        MAPPING_DOC="${2:-}"
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

render_bootstrap_block() {
  local out_file="$1"
  local today
  today="$(date_cn)"

  cat >"$out_file" <<EOF_BLOCK
$START_MARK

## 2. 下一阶段执行蓝图（P5→P6）

### 2.1 目标与边界

1. 保持“真实环境结论优先”，本机参考仅用于预校准，不替代 real-env \`pass\`。
2. 将 P5 从“本机参考通过”推进到“真实环境可冻结”收口。
3. 启动 P6：把 Agent 方案中剩余的三类主缺口变成可执行模块（fairness benchmark 冻结、Claim Graph、Policy Registry）。

### 2.2 模块编排（顺序）

| 模块 | 状态 | 本轮目标 | 验证方式 |
| --- | --- | --- | --- |
| ai-judge-next-plan-bootstrap | 已完成 | 固化下一阶段计划模板与执行顺序 | 脚本回归测试 + plan 文档差异核对 |
| ai-judge-p5-local-reference-evidence-fill | 已完成 | 本机五轨道证据已齐备并达成 \`local_reference_pass\` | \`bash scripts/harness/ai_judge_p5_real_calibration_on_env.sh --allow-local-reference\` |
| ai-judge-p5-real-calibration-on-env | 进行中（local_reference_pass / real_pending） | 真实环境就绪后完成五类轨道 real 证据冻结并达成 \`pass\` | \`bash scripts/harness/ai_judge_p5_real_calibration_on_env.sh\` |
| ai-judge-fairness-gate-implementation-phase2 | 已完成 | panel disagreement + review queue + manual decision 闭环 | \`pytest -q ai_judge_service/tests/test_judge_mainline.py ai_judge_service/tests/test_app_factory.py\` |
| ai-judge-fairness-benchmark-freeze | 待开始 | 冻结 fairness benchmark 阈值与对外口径，形成可审计基线 | benchmark 脚本 + 阈值文档 + 回归 |
| ai-judge-claim-graph-bootstrap | 待开始 | 建立 Claim Graph 最小可用主链（提取/冲突/引用） | domain 单测 + final payload 回归 |
| ai-judge-policy-registry-bootstrap | 待开始 | Prompt/Tool/Policy Registry 最小闭环并接入 runtime | 配置/路由/回归测试 |

### 2.3 验收口径

1. 本机参考口径：允许 \`local_reference_pass\`，但不得覆盖真实环境结论。
2. 真实环境口径：仅 \`status=pass\` 视为 P5 校准完成。
3. P6 口径：每个模块必须给出可执行 DoD、验证命令和证据路径。
4. 文档口径：\`当前开发计划.md\`、\`todo.md\`、\`runtime-verify.md\` 的状态描述保持一致。

### 2.4 风险与阻塞

1. 真实环境样本不足时，统一保持 \`local_reference_*\` 或 \`pending_real_data\`，禁止伪造 real 证据。
2. 若本机采样与真实环境方向冲突，以真实环境结论为准并回写差异说明。
3. Claim Graph / Policy Registry 初版必须保持 hard-cut 主链，不引入长期兼容双轨。

### 2.5 参考资料

1. 章节完成度映射：
   - [AI_Judge_Service-企业级Agent方案-章节完成度映射-2026-04-13.md](/Users/panyihang/Documents/EchoIsle/docs/module_design/AI裁判团/AI_Judge_Service-企业级Agent方案-章节完成度映射-2026-04-13.md)
2. P5 校准脚本：
   - \`scripts/harness/ai_judge_p5_real_calibration_on_env.sh\`
   - \`scripts/harness/ai_judge_calibration_prep.sh\`

### 2.6 Bootstrap 元信息

1. bootstrap_at: \`$today\`
2. bootstrap_source: \`ai-judge-next-plan-bootstrap\`
3. mapping_doc: \`$MAPPING_DOC\`

$END_MARK
EOF_BLOCK
}

update_plan_header_lines() {
  local in_file="$1"
  local out_file="$2"
  local today
  today="$(date_cn)"

  awk -v day="$today" '
    /^更新时间：/ {
      print "更新时间：" day "  "
      next
    }
    /^当前主线：/ {
      print "当前主线：`AI_judge_service 下一阶段（P5 校准与公平门禁补强）`  "
      next
    }
    /^当前状态：/ {
      print "当前状态：进行中（next-plan bootstrapped）"
      next
    }
    { print }
  ' "$in_file" >"$out_file"
}

replace_or_append_block() {
  local plan_file="$1"
  local block_file="$2"
  local out_file="$3"

  if grep -Fq "$START_MARK" "$plan_file" && grep -Fq "$END_MARK" "$plan_file"; then
    local before after
    before="$(mktemp)"
    after="$(mktemp)"

    awk -v s="$START_MARK" '
      index($0, s) { exit }
      { print }
    ' "$plan_file" >"$before"

    awk -v e="$END_MARK" '
      found { print }
      index($0, e) { found = 1 }
    ' "$plan_file" >"$after"

    cat "$before" "$block_file" "$after" >"$out_file"
    rm -f "$before" "$after"
    printf '%s' "replaced"
  else
    cp "$plan_file" "$out_file"
    printf '\n' >>"$out_file"
    cat "$block_file" >>"$out_file"
    printf '%s' "appended"
  fi
}

count_marker_blocks() {
  local file="$1"
  local count
  count="$(grep -F "$START_MARK" "$file" | wc -l | tr -d ' ')"
  printf '%s' "$count"
}

write_json_summary() {
  local operation="$1"
  local marker_count="$2"

  {
    printf '{\n'
    printf '  "run_id": "%s",\n' "$(json_escape "$RUN_ID")"
    printf '  "status": "%s",\n' "$(json_escape "$STATUS")"
    printf '  "root": "%s",\n' "$(json_escape "$ROOT")"
    printf '  "plan_doc": "%s",\n' "$(json_escape "$PLAN_DOC")"
    printf '  "mapping_doc": "%s",\n' "$(json_escape "$MAPPING_DOC")"
    printf '  "operation": "%s",\n' "$(json_escape "$operation")"
    printf '  "bootstrap_marker_count": %s,\n' "$marker_count"
    printf '  "started_at": "%s",\n' "$(json_escape "$STARTED_AT")"
    printf '  "finished_at": "%s",\n' "$(json_escape "$FINISHED_AT")"
    printf '  "outputs": {\n'
    printf '    "json": "%s",\n' "$(json_escape "$EMIT_JSON")"
    printf '    "markdown": "%s"\n' "$(json_escape "$EMIT_MD")"
    printf '  }\n'
    printf '}\n'
  } >"$EMIT_JSON"
}

write_md_summary() {
  local operation="$1"
  local marker_count="$2"

  {
    printf '# AI Judge Next Plan Bootstrap\n\n'
    printf -- '- run_id: `%s`\n' "$RUN_ID"
    printf -- '- status: `%s`\n' "$STATUS"
    printf -- '- operation: `%s`\n' "$operation"
    printf -- '- bootstrap_marker_count: `%s`\n' "$marker_count"
    printf -- '- plan_doc: `%s`\n' "$PLAN_DOC"
    printf -- '- mapping_doc: `%s`\n' "$MAPPING_DOC"
    printf -- '- started_at: `%s`\n' "$STARTED_AT"
    printf -- '- finished_at: `%s`\n' "$FINISHED_AT"
    printf -- '- output_json: `%s`\n' "$EMIT_JSON"
    printf -- '- output_md: `%s`\n' "$EMIT_MD"

    printf '\n## Summary\n\n'
    printf '1. 已同步计划头部状态为 next-plan bootstrapped。\n'
    printf '2. 已幂等写入 P5 下一阶段执行蓝图块。\n'
    printf '3. 可重复执行脚本以替换蓝图块，不会重复追加。\n'
  } >"$EMIT_MD"
}

main() {
  parse_args "$@"
  resolve_root

  if [[ -z "$PLAN_DOC" ]]; then
    PLAN_DOC="$ROOT/docs/dev_plan/当前开发计划.md"
  else
    PLAN_DOC="$(abs_path "$PLAN_DOC")"
  fi
  if [[ -z "$MAPPING_DOC" ]]; then
    MAPPING_DOC="$ROOT/docs/module_design/AI裁判团/AI_Judge_Service-企业级Agent方案-章节完成度映射-2026-04-13.md"
  else
    MAPPING_DOC="$(abs_path "$MAPPING_DOC")"
  fi

  RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-ai-judge-next-plan-bootstrap"
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

  ensure_parent_dir "$EMIT_JSON"
  ensure_parent_dir "$EMIT_MD"

  [[ -f "$PLAN_DOC" ]] || { echo "计划文档不存在: $PLAN_DOC" >&2; exit 1; }

  local temp1 temp2 block_file
  temp1="$(mktemp)"
  temp2="$(mktemp)"
  block_file="$(mktemp)"

  update_plan_header_lines "$PLAN_DOC" "$temp1"
  render_bootstrap_block "$block_file"
  local operation
  operation="$(replace_or_append_block "$temp1" "$block_file" "$temp2")"
  mv "$temp2" "$PLAN_DOC"

  local marker_count
  marker_count="$(count_marker_blocks "$PLAN_DOC")"
  if [[ "$marker_count" != "1" ]]; then
    STATUS="fail"
  fi

  FINISHED_AT="$(iso_now)"
  write_json_summary "$operation" "$marker_count"
  write_md_summary "$operation" "$marker_count"

  echo "ai_judge_next_plan_bootstrap_status: $STATUS"
  echo "summary_json: $EMIT_JSON"
  echo "summary_md: $EMIT_MD"
  echo "operation: $operation"
  echo "bootstrap_marker_count: $marker_count"

  rm -f "$temp1" "$block_file"

  if [[ "$STATUS" != "pass" ]]; then
    exit 1
  fi
}

main "$@"
