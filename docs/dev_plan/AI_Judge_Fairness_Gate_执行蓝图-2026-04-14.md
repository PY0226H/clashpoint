# AI Judge Fairness Gate 执行蓝图

更新时间：2026-04-14
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
