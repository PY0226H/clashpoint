# EchoIsle Harness Docs Overview

更新时间：2026-04-13
状态：P1-1 / P1-2 / P1-3 / P1-4 / P1-5 / P2-4 / P2-5 / P3-1 已完成；module-turn-harness 已退役

---

## 1. 目的

`docs/harness/` 是 EchoIsle 的 agent 规则主目录。

它的职责是：

1. 承接从 `AGENTS.md` 下沉下来的长规则
2. 让 agent 能按主题定位规则，而不是反复通读一个长文件
3. 明确区分：
   - 当前已生效规则
   - 后续阶段计划中的目标形态

---

## 2. 当前阶段说明

当前仍保留并生效的已完成项：

1. `P1-1 AGENTS.md TOC 收敛`
2. `P1-2 docs/harness 规则主目录`
3. `P1-3 活动计划入口与多计划槽位`
4. `P1-4 计划/证据目录职责切分`
5. `P1-5 docs lint 首版`
6. `P2-4 PRD guard 摘要优先`
7. `P2-5 knowledge pack 异步化`
8. `P3-1 journey_verify 统一入口`

已退役内容：

1. `P2-1 module-turn-harness skill`
2. `P2-2 module_turn_harness.sh`
3. `P2-3 module-turn-harness 结构化执行日志`

这意味着：

1. `AGENTS.md` 现在只承担导航职责
2. 规则细节迁移到了 `docs/harness/`
3. 已建立 `default` 活动计划入口与命名 `slot` 机制
4. 新增门禁/预检/验收报告默认已迁移到 `docs/loadtest/evidence/`
5. 已新增 `scripts/quality/harness_docs_lint.sh`，可机检 pointer、活动计划结构与 harness 文档元信息
6. PRD gate 已默认走 `docs/harness/product-goals.md`，高风险模块自动回读完整 PRD
7. explanation/interview 已从默认阻塞链移出，改由 knowledge pack 策略触发
8. 已新增 `scripts/harness/journey_verify.sh`，统一承接 runtime verify profile 分发与摘要输出
9. 日常默认认知入口已调整为 `docs/harness/task-flows/`，按任务类型和生命周期触发 skill
10. `module-turn-harness` 已退役并删除，不再作为入口或可选 wrapper

换句话说：

现在已经完成两层变化：

1. 规则组织方式与查找方式完成收敛
2. 模块级开发回合有了任务类型流程入口
3. 计划回写已支持单计划和并行计划两种使用方式

但以下能力仍未完成：

1. 具体 runtime profile 细化与主链化
2. CI 三层切分
3. docs lint 全量接入 CI
4. knowledge pack 周期补写

---

## 3. 文档地图

1. `10-task-classification.md`
   - 任务分类
   - module-level 判定
   - 当前 task flow 路由

2. `task-flows/`
   - dev/refactor/non-dev/stage-closure 的当前生命周期流程
   - 开发前、开发中、开发后的 skill 触发边界

3. `product-goals.md`
   - 日常模块开发默认读取的产品摘要
   - 高风险任务何时回读完整 PRD

4. `30-runtime-verify.md`
   - 当前验证模型
   - 统一 runtime verify 落地前的暂行做法

5. `40-doc-governance.md`
   - 计划文档
   - 执行证据
   - explanation/interview 的当前职责

6. `50-quality-gates.md`
   - 当前质量门禁
   - CI 和局部 guard 的职责分工

7. `60-usage-tutorial.md`
   - 当前已落地 harness 的完整使用教程
   - 日常开发、并行计划、slot/plan、journey verify 的实际用法

---

## 4. 使用原则

1. 先看 `AGENTS.md`，确定当前任务属于哪类问题。
2. 再按主题跳到对应 harness 文档，而不是一次性读完整个目录。
3. 如果文档里写了“当前已生效”，按规则执行。
4. 如果文档里写了“后续目标形态”，不要提前当成当前规则使用。

---

## 5. 当前不变的事实

1. 权威 PRD 仍然是 `docs/PRD/在线辩论AI裁判平台完整PRD.md`
2. 当前默认认知入口为 `docs/harness/task-flows/`，既有 skill 按生命周期触发
3. 当前 `build.yml` 仍然是主要 CI workflow
4. 当前已引入统一 runtime verify 入口，但尚未接入普通开发主链
5. 当前已把 explanation/interview 切到 knowledge pack 策略，但还没有周期补写
