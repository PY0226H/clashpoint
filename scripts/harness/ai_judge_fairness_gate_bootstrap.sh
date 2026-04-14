#!/usr/bin/env bash
set -euo pipefail

ROOT=""
OUTPUT_DOC=""
OUTPUT_ENV=""
EMIT_JSON=""
EMIT_MD=""
RUN_ID=""
STARTED_AT=""
FINISHED_AT=""
STATUS="pass"

usage() {
  cat <<'USAGE'
用法:
  ai_judge_fairness_gate_bootstrap.sh \
    [--root <repo-root>] \
    [--output-doc <path>] \
    [--output-env <path>] \
    [--emit-json <path>] \
    [--emit-md <path>]

说明:
  - 生成公平门禁 bootstrap 执行蓝图（swap/style/panel）。
  - 生成公平门禁证据模板，便于后续真实实现阶段填充。
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

write_bootstrap_doc() {
  local file="$1"
  local today="$2"

  cat >"$file" <<EOF_DOC
# AI Judge Fairness Gate 执行蓝图

更新时间：$today
状态：bootstrap ready

## 1. 目标

1. 在不依赖真实环境的前提下，先冻结公平门禁实施路径。
2. 将 swap/style/panel 三类公平风险转为可执行工作包。
3. 明确与现有 AI judge 主链的继承点，避免推倒重来。

## 2. 继承能力

1. 输入盲化拒绝和 failed callback 已落地，可复用为公平门禁入口防线。
2. trace/replay 与审计告警主链已落地，可复用为公平门禁证据账本。
3. final 报告结构化展示已落地，可增量挂载 fairness summary 字段。
4. style_mode 和 rejudge 能力已存在，可直接承接 style/panel 门禁实现。

## 3. 工作包

### FG-1 label swap instability

1. 增加标签互换重算路径（pro/con 对调）。
2. 输出 swap instability 指标与 alert 阈值。
3. 若 instability 超阈值，强制降级到 draw 或 review_required。

### FG-2 style perturbation instability

1. 固定同案多 style_mode 重算（rational、strict、neutral）。
2. 统计 winner 漂移与评分偏移。
3. 若 style instability 超阈值，触发 fairness alert。

### FG-3 panel disagreement gate

1. 在现有主链基础上引入轻量 panel 复判（独立 seeds/temperature）。
2. 计算 panel disagreement 指标。
3. disagreement 超阈值时，进入受保护复核而非强判。

## 4. 交付物

1. 公平门禁实现任务清单（代码级）。
2. fairness report 数据结构（内部字段 + 用户可展示摘要）。
3. 统一 alert 命名与错误语义（label_swap_instability、style_shift_instability、judge_panel_high_disagreement）。
4. 回归测试矩阵（unit + route + mainline）。

## 5. 验收标准

1. 三类门禁均有可复现测试与阈值配置入口。
2. 触发门禁时，回调和 trace 能稳定留痕。
3. 不影响当前 phase/final 主链成功路径。
4. 文档、计划、证据模板三者一致。

## 6. 后续顺序

1. 第一阶段：实现 swap/style 基线门禁（不引入多模型）。
2. 第二阶段：实现 panel disagreement 与 review 流程。
3. 第三阶段：接入真实环境 benchmark 并冻结阈值。
EOF_DOC
}

write_bootstrap_env() {
  local file="$1"
  local today="$2"

  cat >"$file" <<EOF_ENV
FAIRNESS_GATE_BOOTSTRAP_STATUS=prepared
BOOTSTRAP_UPDATED_AT=${today}T00:00:00Z
LABEL_SWAP_GATE_PLAN=ready
STYLE_PERTURBATION_GATE_PLAN=ready
PANEL_DISAGREEMENT_GATE_PLAN=ready
FAIRNESS_REPORT_SCHEMA_PLAN=ready
REAL_ENV_REQUIRED_FOR_BOOTSTRAP=false
NOTES=bootstrap_only_no_threshold_freeze
EOF_ENV
}

write_json_summary() {
  {
    printf '{\n'
    printf '  "run_id": "%s",\n' "$(json_escape "$RUN_ID")"
    printf '  "status": "%s",\n' "$(json_escape "$STATUS")"
    printf '  "root": "%s",\n' "$(json_escape "$ROOT")"
    printf '  "output_doc": "%s",\n' "$(json_escape "$OUTPUT_DOC")"
    printf '  "output_env": "%s",\n' "$(json_escape "$OUTPUT_ENV")"
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
  {
    printf '# AI Judge Fairness Gate Bootstrap\n\n'
    printf -- '- run_id: `%s`\n' "$RUN_ID"
    printf -- '- status: `%s`\n' "$STATUS"
    printf -- '- output_doc: `%s`\n' "$OUTPUT_DOC"
    printf -- '- output_env: `%s`\n' "$OUTPUT_ENV"
    printf -- '- started_at: `%s`\n' "$STARTED_AT"
    printf -- '- finished_at: `%s`\n' "$FINISHED_AT"
  } >"$EMIT_MD"
}

main() {
  parse_args "$@"
  resolve_root

  if [[ -z "$OUTPUT_DOC" ]]; then
    OUTPUT_DOC="$ROOT/docs/dev_plan/AI_Judge_Fairness_Gate_执行蓝图-$(date_cn).md"
  else
    OUTPUT_DOC="$(abs_path "$OUTPUT_DOC")"
  fi

  if [[ -z "$OUTPUT_ENV" ]]; then
    OUTPUT_ENV="$ROOT/docs/loadtest/evidence/ai_judge_fairness_gate_bootstrap.env"
  else
    OUTPUT_ENV="$(abs_path "$OUTPUT_ENV")"
  fi

  RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-ai-judge-fairness-gate-bootstrap"
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

  ensure_parent_dir "$OUTPUT_DOC"
  ensure_parent_dir "$OUTPUT_ENV"
  ensure_parent_dir "$EMIT_JSON"
  ensure_parent_dir "$EMIT_MD"

  local today
  today="$(date_cn)"

  write_bootstrap_doc "$OUTPUT_DOC" "$today"
  write_bootstrap_env "$OUTPUT_ENV" "$today"

  FINISHED_AT="$(iso_now)"
  write_json_summary
  write_md_summary

  echo "ai_judge_fairness_gate_bootstrap_status: $STATUS"
  echo "output_doc: $OUTPUT_DOC"
  echo "output_env: $OUTPUT_ENV"
  echo "summary_json: $EMIT_JSON"
  echo "summary_md: $EMIT_MD"
}

main "$@"
