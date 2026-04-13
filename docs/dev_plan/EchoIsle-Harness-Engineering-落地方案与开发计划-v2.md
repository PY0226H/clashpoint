# EchoIsle Harness Engineering 落地方案与开发计划 v2

更新时间：2026-04-13
状态：执行版（v2）
适用范围：EchoIsle 仓库内 Codex/agent 驱动的模块级开发、验证、计划回写、CI 门禁与文档治理
参考文章：[Harness engineering: leveraging Codex in an agent-first world](https://openai.com/index/harness-engineering/)

---

## 0. 文档定位

本文档分为两部分：

1. 第一部分给出 EchoIsle 的 Harness Engineering 落地方案 v2，明确目标形态、接口约定、目录策略、门禁分层与 agent 工作方式。
2. 第二部分给出完整开发计划，包含阶段拆分、任务编号、输入输出、验收标准、依赖关系与切换策略。

本文档是本轮 EchoIsle Harness Engineering 升级的主计划文档。后续执行阶段，活动计划默认应通过 `.codex/plan-slots/default.txt` 指向 `docs/dev_plan/当前开发计划.md`，并在并行计划场景通过命名 slot 管理。

2026-04-13 当前口径修正：

1. `module-turn-harness` 已退役并删除，不再作为普通 dev/refactor 的默认开工入口。
2. 日常默认入口调整为 `docs/harness/task-flows/`，按任务类型和生命周期触发具体 skill。
3. 不再保留 `module-turn-harness` 可选包装工具；后续不要继续规划增强或恢复该 wrapper。
4. 本文档早期章节中“module-turn-harness 默认入口 / 唯一默认入口”的设计描述视为历史方案，不再代表当前执行口径。

---

## 第一部分：落地方案 v2

## 1. 当前现状与核心问题

### 1.1 已有基础

EchoIsle 当前已经具备明显的 harness 雏形：

1. `AGENTS.md` 已定义技能目录、任务分类、pre/post hook matrix。
2. 已有多个强制性 skill：
   - `pre-module-prd-goal-guard`
   - `post-module-test-guard`
   - `post-module-plan-sync`
   - `post-optimization-plan-sync`
   - `post-module-explanation-journal`
   - `post-module-interview-journal`
   - `post-module-commit-message`
3. 已存在部分机械化 guard：
   - oversized file check
   - release/preflight/supply-chain 系列脚本
   - 迁移/专项质量脚本（如 `scripts/quality/verify_chat_migrations_fresh.sh`）
4. 已有部分结构化计划与矩阵文档：
   - `docs/dev_plan/todo.md`
   - `docs/dev_plan/completed.md`
   - `docs/dev_plan/前端开发计划.md`
   - `docs/dev_plan/前端开发计划_Phase0执行矩阵.md`
5. 已有架构基线文档：
   - `docs/architecture/服务边界清单-2026-03-09.md`
   - `docs/architecture/重构兼容与回滚模板.md`

### 1.2 当前主要问题

尽管已有很多规则和脚本，但整体仍然更接近“强规则 + 多 hook”的流程集合，而不是一个完整的 harness 系统。

主要问题如下：

1. 缺少单一 orchestrator。
   现在的 pre/post skills 已经很多，但默认仍依赖 agent 记住顺序和适用矩阵，未形成“一个入口驱动整轮交付”的总控层。

2. 运行态验证不在主链路。
   当前流程强于“事后补文档”，弱于“当回合就验证运行态是否正确”。agent 能看到 diff、测试结果，却缺少统一的业务旅程、日志、trace、指标摘要入口。

3. PRD 对齐成本过高。
   `pre-module-prd-goal-guard` 当前要求每次模块级开发都完整阅读 PRD 全文。该策略能防跑偏，但默认信息量过大，不利于 progressive disclosure。

4. 文档沉淀偏重，决策入口偏弱。
   `docs/explanation`、`docs/interview` 已经形成大量历史沉淀，但缺少索引、清理和“当前回合如何消费这些文档”的机制，容易从知识库变成档案库。

5. 计划文档定位仍不够稳定。
   `post-module-plan-sync` 虽然支持动态探测计划文档，但默认仍有猜测成本；`docs/dev_plan/当前开发计划.md` 与 `docs/dev_plan/当前开发文档.md` 目前为空，不能承担明确指针作用。

6. CI 仍是单体式 workflow。
   `.github/workflows/build.yml` 同时承担 PR、全量、release preflight 责任，且多个报告仍默认输出到 `docs/dev_plan/`，与“计划目录只存计划”的语义冲突。

### 1.3 本次升级的默认取舍

本方案默认采用以下决策：

1. 升级节奏：`强切主线`
   不长期维持双轨。会采用阶段化实施，但每阶段完成后立即切到新主路径。

2. 文档主链策略：`explanation/interview 改为异步沉淀`
   保留其价值，但不再让它们阻塞每次模块级开发回合。

3. 总体策略：`增量重构实现，强制切换入口`
   尽量复用现有 skills/scripts 的内部能力，但外部默认入口切到新的 `module-turn-harness`。

---

## 2. 目标与成功标准

### 2.1 总目标

把 EchoIsle 从“由规则和钩子堆出来的 agent 使用流程”，升级为“对 agent 高可读、对运行态高可见、对规则高可机检、对文档可持续治理”的 harness 系统。

### 2.2 成功标准

同时满足以下条件时，视为升级成功：

1. `AGENTS.md` 收敛为 TOC，不再承载长篇细则。
2. 模块级开发具备稳定流程入口；历史设计曾计划由 `module-turn-harness` 单一入口编排，但 2026-04-13 已修正为默认读取 `docs/harness/task-flows/`，且 `module-turn-harness` 已退役删除。
3. 运行态验证进入主链路，agent 默认能拿到旅程验证、日志、指标、trace 摘要。
4. `docs/dev_plan` 只存计划，不再默认接收执行报告。
5. `docs/explanation` / `docs/interview` 变成“可索引、可补写、可清理”的沉淀层。
6. 存在稳定的活动计划入口与多计划槽位机制，计划回写不再依赖猜测，且支持并行开发计划。
7. CI 分为 `PR fast gate`、`nightly full gate`、`release preflight gate` 三层。
8. 新增 docs lint 与 doc-gardening，持续抑制文档熵增。

---

## 3. 设计原则

### 3.1 Repo as system of record

规则、入口、计划、验证、证据路径必须在仓库内有稳定位置，不依赖口头约定或 agent 的临时记忆。

### 3.2 Progressive disclosure

默认只给 agent 足够完成当前任务的信息；完整 PRD、历史讲解、长文档只在高风险或需要追溯时展开。

### 3.3 Mechanical enforcement first

凡是高频、稳定、可枚举的约束，优先转成脚本、lint、gate、结构化日志，而不是继续堆自然语言指令。

### 3.4 Runtime evidence over narrative confidence

对于模块级开发的收口，应优先证明“它真的跑起来且行为正确”，而不是只证明“代码写完了”或“文档已经补了”。

### 3.5 Continuous cleanup

文档与证据目录不是一次性整理，而是持续巡检和回收；历史文档可以保留，但必须可索引、可判定新旧、可发现过期。

---

## 4. 目标形态

## 4.1 顶层入口形态

新增：

1. `skills/module-turn-harness/SKILL.md`
2. `scripts/harness/module_turn_harness.sh`
3. `scripts/harness/journey_verify.sh`
4. `docs/harness/` 规则主目录
5. `.codex/plan-slots/default.txt`

历史设计：模块级开发以 `module-turn-harness` 为唯一默认入口。当前已修正为：模块级开发默认先读 `docs/harness/task-flows/`，其它 pre/post skills 保留为 leaf skills，并按开发前/开发后生命周期触发；`module-turn-harness` 已退役删除。

## 4.2 当前回合的标准交付链

### `dev` 回合

1. 读取任务参数与活动计划入口/命名 slot。
2. 执行 PRD 摘要对齐，必要时回读完整 PRD。
3. 执行测试变更检查与测试门禁。
4. 执行 runtime verify。
5. 执行计划回写。
6. 生成 commit message 建议。
7. 按策略决定是否触发 knowledge pack。
8. 产出结构化执行日志与结论摘要。

### `refactor` 回合

1. 读取任务参数与活动计划入口/命名 slot。
2. 执行 PRD 摘要对齐，必要时回读完整 PRD。
3. 执行测试变更检查与测试门禁。
4. 执行 runtime verify。
5. 执行 optimization plan sync。
6. 生成 commit message 建议。
7. 按策略决定是否触发 knowledge pack。
8. 产出结构化执行日志与结论摘要。

### `non-dev` 回合

1. 只执行与本次任务相关的 docs lint / 静态检查。
2. 不触发模块级 PRD/test/plan sync 流程。
3. 保持轻量，不伪装为“开发完成回合”。

## 4.3 PRD 对齐形态

保留：

- `/Users/panyihang/Documents/EchoIsle/docs/PRD/在线辩论AI裁判平台完整PRD.md`

新增：

- `docs/harness/product-goals.md`

默认策略：

1. 先读取 `product-goals.md`。
2. 如果任务属于以下任一情况，再强制回读完整 PRD：
   - 新产品域
   - 跨服务边界变更
   - 支付 / 鉴权 / AI 裁判主流程
   - 摘要信息不足以判断边界
   - 当前方案可能与非目标范围冲突
3. 最终输出固定结论：
   - 用户价值
   - 关键流程
   - 非目标
   - 本次模块对齐结论
   - 偏离与修正策略（如有）

## 4.4 文档沉淀形态

`post-module-explanation-journal` 与 `post-module-interview-journal` 保留，但定位调整：

1. 默认不阻塞模块级开发主链。
2. 作为 `knowledge pack` 异步沉淀层存在。
3. 在以下场景自动触发：
   - `--knowledge-pack force`
   - 安全/可靠性/架构/跨服务/发布相关模块
   - 需要复盘或面试沉淀的重大模块
   - 每周巡检补写

新增索引要求：

1. `docs/explanation/README.md`
2. `docs/interview/README.md`

每个索引最少包含：

1. 文档分类
2. 最近 20 篇文档入口
3. 模块 -> 文档映射
4. 历史 legacy 路径说明
5. 过期/废弃约定

## 4.5 运行态验证形态

新增统一脚本：

- `scripts/harness/journey_verify.sh`

用于把“我觉得改好了”收敛成“关键旅程跑过了，证据在这里”。

初版 profile：

1. `auth`
   - signin/password
   - refresh
   - sms send
   - bind phone（按环境能力裁剪）

2. `lobby`
   - topics list
   - sessions list
   - join session

3. `room`
   - messages list
   - ws connect / replay / ack 基础路径

4. `judge-ops`
   - report read
   - replay preview
   - replay execute 或只读 ops 旅程

5. `release`
   - 聚合现有 release/preflight/supply-chain 脚本

每次 runtime verify 统一输出：

1. `summary.json`
2. `summary.md`
3. 关联日志路径
4. 关联 trace 路径
5. 指标摘要路径

## 4.6 计划文档形态

新增稳定活动计划入口：

1. `.codex/plan-slots/default.txt`
2. `.codex/plan-slots/<slot>.txt`

计划解析优先级固定为：

1. `--plan`
2. `--slot`
3. `POST_MODULE_ACTIVE_PLAN` / `ACTIVE_PLAN_DOC` / `PLAN_DOC`
4. `POST_MODULE_PLAN_SLOT` / `ACTIVE_PLAN_SLOT` / `PLAN_SLOT`
5. `.codex/plan-slots/*.txt`
6. 最后才做 legacy fallback 自动探测

`docs/dev_plan/当前开发计划.md` 保留为默认活动计划文档，用于单计划时期的“生成计划 -> 执行 -> 回写 -> 收口”闭环。

`docs/dev_plan/当前开发文档.md` 退役，不再承担职责。

## 4.7 CI 形态

当前 `build.yml` 拆为三层：

1. `pr-fast-gate.yml`
2. `nightly-full-gate.yml`
3. `release-preflight.yml`

职责划分：

### PR Fast Gate

目标：快速给出可修复反馈。

至少包含：

1. 路径感知格式/编译/测试子集
2. `harness_docs_lint`
3. 必要的 runtime verify 子集

### Nightly Full Gate

目标：保持全量覆盖。

至少包含：

1. 全量 Rust gate
2. 全量 frontend smoke / Playwright smoke
3. docs lint
4. 全量 journey verify matrix
5. supply chain 巡检

### Release Preflight

目标：发布前硬门禁。

至少包含：

1. 现有 preflight / chaos / SBOM / allowlist / security gate
2. 统一 evidence 与报告输出目录
3. 仅在 release/tag 场景触发

---

## 5. 目录与接口约定

## 5.1 新目录约定

```text
docs/
  harness/
    00-overview.md
    10-task-classification.md
    20-orchestration.md
    30-runtime-verify.md
    40-doc-governance.md
    50-quality-gates.md

scripts/
  harness/
    module_turn_harness.sh
    journey_verify.sh

artifacts/
  harness/
    <timestamp>-<module>.jsonl
    <timestamp>-<module>-summary.md
    <timestamp>-<module>-summary.json

.codex/
  plan-slots/
    default.txt
    <slot>.txt
```

## 5.2 `module_turn_harness.sh` 命令接口

固定参数：

```bash
bash scripts/harness/module_turn_harness.sh \
  --task-kind <dev|refactor|non-dev> \
  --module "<module-id>" \
  --summary "<one-line-summary>" \
  [--plan "<path>"] \
  [--slot "<slot-name>"] \
  [--runtime-profile "<auto|none|auth|lobby|room|judge-ops|release>"] \
  [--knowledge-pack "<auto|skip|force>"] \
  [--dry-run] \
  [--strict]
```

行为要求：

1. `--dry-run` 只输出计划执行链，不改 repo-tracked 文件。
2. `--strict` 任一步失败即终止，并产出结构化失败摘要。
3. 默认写结构化日志到 `artifacts/harness/`。

## 5.3 `journey_verify.sh` 命令接口

固定参数：

```bash
bash scripts/harness/journey_verify.sh \
  --profile "<auth|lobby|room|judge-ops|release>" \
  --emit-json "<path>" \
  --emit-md "<path>" \
  [--collect-logs] \
  [--collect-metrics] \
  [--collect-trace]
```

输出要求：

1. JSON 可机读，供 CI 和 orchestrator 判断。
2. Markdown 供人类快速审阅。
3. 若证据缺失，应显式标记为 `evidence_missing`，而不是静默成功。

## 5.4 `knowledge pack` 策略接口

参数：

- `auto`
- `skip`
- `force`

默认 `auto` 的触发规则固定为：

1. 模块属于 `security` / `reliability` / `architecture` / `cross-service` / `release`
2. 模块有复杂故障修复过程
3. 模块将被频繁复述或复盘
4. 每周 doc-gardener 巡检要求补写

## 5.5 `harness_docs_lint.sh` 检查范围

至少检查以下项：

1. 计划文档必需章节存在
2. 状态词合法性
3. 文件路径存在性
4. 代码证据路径有效性
5. evidence 路径有效性
6. legacy 路径引用
7. `.codex/plan-slots/default.txt` 是否存在且指向有效文档
8. 命名 slot 是否指向有效文档且不存在悬空路径

输出：

1. `json`
2. `markdown`

---

## 6. 非目标与风险控制

### 6.1 本次升级的非目标

1. 不重写所有现有 skills 的业务语义。
2. 不一次性清理全部历史 explanation/interview 文档。
3. 不在第一阶段引入复杂 AST/语义级规则引擎。
4. 不为了“agent 友好”牺牲发布门禁的严肃性。

### 6.2 主要风险

1. 强切主线后，旧工作习惯可能和新入口冲突。
2. runtime verify 初版容易因为环境依赖不稳定而误报。
3. docs lint 首版若规则过严，可能导致大量历史问题阻塞当前开发。
4. explanation/interview 降为异步后，若没有周巡检，沉淀质量可能下滑。

### 6.3 控制策略

1. 所有强切动作必须配套明确 fallback。
2. docs lint 分为 `error` 与 `warning` 两级，历史问题先以 warning 收敛。
3. runtime verify 先做少量稳定 profile，再逐步扩大。
4. knowledge pack 通过每周巡检兜底，避免完全失去沉淀。

---

## 7. 方案验收标准

### 7.1 结构验收

1. `AGENTS.md` 收敛为 TOC。
2. `docs/harness/` 已建立并可稳定定位规则。
3. `.codex/plan-slots/default.txt` 生效，且并行计划可通过命名 slot 区分。
4. `docs/dev_plan` 不再承载默认执行报告。

### 7.2 流程验收

1. 任一模块级回合可通过 `module-turn-harness` 完成。
2. `dev/refactor/non-dev` 三类任务映射稳定。
3. leaf skills 不再依赖人工顺序记忆。

### 7.3 运行态验收

1. 至少已有 `auth/lobby/room/judge-ops` 四个 profile。
2. 每个 profile 都能产出结构化摘要。
3. 失败时能区分代码失败与环境失败。

### 7.4 CI 验收

1. PR fast gate、nightly full gate、release preflight 各自独立。
2. 报告与 evidence 输出路径一致。
3. 旧 `build.yml` 不再承担全部职责。

### 7.5 文档治理验收

1. explanation/interview 目录存在索引。
2. docs lint 可机读。
3. doc-gardener 能稳定发现断链、过期状态、legacy 路径。

---

## 第二部分：完整开发计划

## 8. 开发策略总览

### 8.1 总体策略

开发顺序采用：

1. 先打通信息架构与目录语义
2. 再建立单入口 orchestrator
3. 再补运行态验证
4. 再拆 CI
5. 最后做持续治理

原因：

1. 如果没有统一入口，后续 runtime verify 和 docs lint 都没有稳定挂点。
2. 如果没有活动计划入口与 plan slots，plan sync 在单计划与并行计划之间都会不稳定。
3. 如果先做 doc-gardening 而不先做结构收敛，会不断返工。

### 8.2 执行阶段

本计划拆为 5 个阶段：

1. Phase 1：基础重构与规则主目录
2. Phase 2：单入口 orchestrator
3. Phase 3：运行态验证主链化
4. Phase 4：CI 分层切换
5. Phase 5：文档治理与持续巡检

---

## 9. Phase 1：基础重构与规则主目录

### P1-1 `AGENTS.md` TOC 收敛（已完成，2026-04-06）

- 目标：将 `AGENTS.md` 从规则全集收敛为目录入口。
- 输入：
  - 当前 `AGENTS.md`
  - 现有 skills 列表
  - 当前强制规则
- 动作：
  1. 把长规则下沉到 `docs/harness/`
  2. `AGENTS.md` 只保留原则、技能目录、入口链接、强制摘要
  3. 补充 `module-turn-harness` 的默认入口说明
- 产出：
  1. 精简后的 `AGENTS.md`
  2. `docs/harness/00-overview.md`
  3. `docs/harness/10-task-classification.md`
- 验收：
  1. `AGENTS.md` 不再承载长篇细则
  2. 能在 2 分钟内定位规则入口

- 当前完成情况：
  1. 已将 `/Users/panyihang/Documents/EchoIsle/AGENTS.md` 收敛为 TOC 入口，保留技能目录、任务分类、强制 hook 摘要与 `docs/harness/` 导航
  2. 已补充 `module-turn-harness` 作为当前模块级默认入口说明
  3. 原先长规则已下沉到 `docs/harness/` 主目录，不再继续堆叠在 `AGENTS.md`

### P1-2 新建 `docs/harness/` 规则主目录（已完成，2026-04-06）

- 目标：把规则沉淀为 agent 可导航的文档层。
- 输入：
  - `AGENTS.md`
  - 现有 skill 规则
  - 架构和计划文档
- 动作：
  1. 新建以下文件：
     - `00-overview.md`
     - `20-orchestration.md`
     - `30-runtime-verify.md`
     - `40-doc-governance.md`
     - `50-quality-gates.md`
  2. 每个文档只写稳定规则，不写临时阶段说明
- 产出：
  - `docs/harness/*.md`
- 验收：
  1. 规则边界清晰
  2. `AGENTS.md` 中所有关键规则都有落点

- 当前完成情况：
  1. 已建立 `docs/harness/` 主目录，并落地以下文件：
     - `00-overview.md`
     - `10-task-classification.md`
     - `20-orchestration.md`
     - `30-runtime-verify.md`
     - `40-doc-governance.md`
     - `50-quality-gates.md`
  2. 已将 `AGENTS.md` 中的导航链接对齐到上述文档
  3. 当前文档内容已明确区分“现状规则”和“后续阶段目标”，避免把未来设计误判为已生效规则

### P1-3 引入活动计划入口与多计划槽位（已完成，2026-04-06）

- 目标：让计划回写默认有稳定目标，同时兼容并行推进多个短期开发计划。
- 输入：
  - 当前 `post-module-plan-sync`
  - 当前 `post-optimization-plan-sync`
  - `docs/dev_plan` 现状
- 动作：
  1. 新建 `.codex/plan-slots/default.txt`，默认指向 `docs/dev_plan/当前开发计划.md`
  2. 约定 `.codex/plan-slots/<slot>.txt` 作为命名计划槽位，例如 `backend.txt`、`frontend.txt`
  3. 保留 `docs/dev_plan/当前开发计划.md` 作为单计划时期的默认活动计划文件，而不是退役为 pointer 页面
  4. 明确 `todo.md`、`completed.md` 作为长期沉淀层；活动计划只在阶段收口时整合进入长期文档
  5. 明确解析顺序：`--plan` > `--slot` > `default` 槽位 > 单活动计划回退；若检测到多个活动计划且未显式指定，则禁止猜测
- 产出：
  1. `.codex/plan-slots/default.txt`
  2. `docs/dev_plan/当前开发计划.md` 的活动计划约定
  3. 多计划槽位规则说明
- 验收：
  1. 单计划场景下 plan sync 默认稳定回写 `docs/dev_plan/当前开发计划.md`
  2. 多计划并行场景下可通过 `--slot` 或 `--plan` 稳定区分目标
  3. 当存在多个活动计划且缺少显式目标时，系统不会猜测回写对象

- 当前完成情况：
  1. 已新增 `.codex/plan-slots/default.txt`，默认指向 `docs/dev_plan/当前开发计划.md`
  2. 已将 `post-module-plan-sync`、`post-optimization-plan-sync`、`module-turn-harness` 全部升级为支持 `--slot`
  3. 已建立 `docs/dev_plan/active/README.md`，明确并行计划的活动文档组织方式
  4. 已将“单计划 / 并行计划 / 收口整合”使用规则写入 `docs/harness`

### P1-4 计划/证据目录职责切分（已完成，2026-04-06）

- 目标：确保 `docs/dev_plan` 只承载计划。
- 输入：
  - `.github/workflows/build.yml`
  - 现有 release/supply chain 脚本
- 动作：
  1. 盘点所有默认 `--report-out` 指向 `docs/dev_plan` 的脚本
  2. 将默认输出迁移到 `docs/loadtest/evidence` 或 `docs/consistency_reports`
  3. 保留 CLI 参数兼容
- 产出：
  1. 更新后的脚本默认值
  2. 更新后的 evidence 目录约定
- 验收：
  1. 新增执行报告不再默认写入 `docs/dev_plan`
  2. 现有调用不被破坏

- 当前完成情况：
  1. 已将 `v2d_stage_acceptance_gate.sh`、`ai_judge_m7_stage_acceptance_gate.sh`、`supply_chain_*` 系列脚本的默认 `--report-out` 迁移到 `docs/loadtest/evidence/`
  2. 已同步 `appstore_preflight_check.sh` 的派生默认报告路径
  3. 已同步 `.github/workflows/build.yml` 的 CI 输出与 artifact 上传路径
  4. 已同步 `ai_judge_service/README.md` 的示例命令，避免继续把报告写入 `docs/dev_plan`

### P1-5 docs lint 首版（已完成，2026-04-06）

- 目标：把计划与文档结构转成可机检约束。
- 输入：
  - `docs/dev_plan/todo.md`
  - `docs/dev_plan/completed.md`
  - `.codex/plan-slots/default.txt`
  - `docs/harness/*.md`
- 动作：
  1. 新建 `scripts/quality/harness_docs_lint.sh`
  2. 检查必需章节、状态词、路径、pointer、一致性
  3. 输出 `json + markdown`
- 产出：
  1. docs lint 脚本
  2. lint 规则说明
- 验收：
  1. 本地可执行
  2. 可被 CI 调用
  3. 对故意构造的断链/空 pointer 稳定报错
- 当前完成情况：
  1. 已新增 `scripts/quality/harness_docs_lint.sh`
  2. 已覆盖 `.codex/plan-slots/*.txt`、`当前开发计划.md`、`todo.md`、`completed.md`、`docs/harness/*.md` 的首版规则
  3. 已输出 `json + markdown` 报告，并补齐 `scripts/quality/tests/test_harness_docs_lint.sh`
  4. 已将 `module-turn-harness --task-kind non-dev` 接入 docs lint 轻量检查

### Phase 1 验收门槛

1. `AGENTS.md` 已 TOC 化
2. `docs/harness/` 已建立
3. 活动计划入口与 plan slot 机制已可用
4. docs lint 首版可运行
5. 计划/证据目录职责已切分

当前进度（2026-04-06）：

1. 第 1 项已完成
2. 第 2 项已完成
3. 第 3 项已完成
4. 第 4 项已完成
5. 第 5 项已完成

---

## 10. Phase 2：单入口 orchestrator

### P2-1 新建 `module-turn-harness` skill（已完成，2026-04-06）

- 目标：提供唯一模块级入口。
- 输入：
  - 当前 pre/post skills
  - `AGENTS.md` hook matrix
- 动作：
  1. 新建 `skills/module-turn-harness/SKILL.md`
  2. 说明适用范围、参数、执行链、失败策略
  3. 在 `AGENTS.md` 中将其标记为默认主入口
- 产出：
  - `skills/module-turn-harness/SKILL.md`
- 验收：
  1. 文档可独立指导 agent 使用
  2. 与 task classification 保持一致
  3. 已完成

### P2-2 新建 `module_turn_harness.sh`（已完成，2026-04-06）

- 目标：让模块级回合可机械编排。
- 输入：
  - 现有 skills/scripts
   - Phase 1 的活动计划入口/plan slots 和 docs lint
- 动作：
  1. 新建 `scripts/harness/module_turn_harness.sh`
  2. 支持 `dev/refactor/non-dev`
  3. 支持 `--dry-run`
  4. 支持 `--strict`
  5. 调用 leaf skills 与 runtime verify
- 产出：
  - `scripts/harness/module_turn_harness.sh`
  - `scripts/harness/tests/test_module_turn_harness.sh`
- 验收：
  1. dry-run 能输出执行链
  2. 三种 task-kind 映射正确
  3. 失败时有稳定返回码
  4. 已完成

### P2-3 结构化执行日志（已完成，2026-04-06）

- 目标：让每次回合执行过程可追踪。
- 输入：
  - `module_turn_harness.sh`
- 动作：
  1. 为每个步骤记录开始/结束/退出码/证据路径
  2. 输出到 `artifacts/harness/*.jsonl`
  3. 同步生成 `summary.md` 和 `summary.json`
- 产出：
  - `artifacts/harness/<timestamp>-<module>.jsonl`
- 验收：
  1. 任一步失败可定位
  2. 成功回合可完整复盘
- 当前完成情况：
  1. 已在 `module_turn_harness.sh` 中为各步骤记录开始/结束/退出码/证据路径
  2. 已默认输出 `artifacts/harness/<timestamp>-<module>.jsonl`
  3. 已同步生成 `artifacts/harness/<timestamp>-<module>.summary.json` 与 `.summary.md`
  4. 已补齐 `scripts/harness/tests/test_module_turn_harness.sh` 的 execute 模式回归

### P2-4 PRD guard 升级为摘要优先（已完成，2026-04-06）

- 目标：降低默认上下文成本，同时保留高风险兜底。
- 输入：
  - 完整 PRD
  - 当前 `pre-module-prd-goal-guard`
- 动作：
  1. 新建 `docs/harness/product-goals.md`
  2. 调整 `pre-module-prd-goal-guard`
  3. 增加“何时回读全文 PRD”的明规则
- 产出：
  1. `product-goals.md`
  2. 升级后的 PRD guard
- 验收：
  1. 普通模块默认走摘要
  2. 高风险模块能自动回读全文
- 当前完成情况：
  1. 已新增 `docs/harness/product-goals.md` 作为默认产品摘要入口
  2. 已新增 `skills/pre-module-prd-goal-guard/scripts/run_prd_goal_guard.sh`
  3. `module_turn_harness.sh` 已接入独立 PRD guard，并支持 `--prd-mode auto|summary|full`
  4. 已补齐 `skills/pre-module-prd-goal-guard/scripts/tests/test_run_prd_goal_guard.sh`

### P2-5 knowledge pack 改为异步（已完成，2026-04-06）

- 目标：把 explanation/interview 从主阻塞链移出。
- 输入：
  - `post-module-explanation-journal`
  - `post-module-interview-journal`
- 动作：
  1. 明确 `auto|skip|force`
  2. 在 orchestrator 中挂接
  3. 不再默认阻塞小回合开发
- 产出：
  - orchestrator 的 knowledge pack 策略
- 验收：
  1. 默认不阻塞
  2. 高风险模块能自动触发
- 当前完成情况：
  1. `module_turn_harness.sh` 已新增 `--knowledge-pack auto|skip|force`
  2. explanation/interview 已从默认阻塞链移出，改为 knowledge pack 决策后触发
  3. `auto` 已支持 `security / reliability / architecture / cross-service / release` 与复杂故障修复场景自动触发
  4. 已补齐 `scripts/harness/tests/test_module_turn_harness.sh` 对 `auto/force` 的回归覆盖

### Phase 2 验收门槛

1. `module-turn-harness` 已成为默认入口
2. Orchestrator 有 dry-run 与 strict
3. PRD guard 已改为摘要优先
4. knowledge pack 已脱离主阻塞链
5. 执行日志可结构化输出

---

## 11. Phase 3：运行态验证主链化

### P3-1 新建 `journey_verify.sh`

- 目标：统一业务旅程验证入口。
- 输入：
  - 当前 smoke/e2e/release 脚本
  - 现有 auth/debate/ops 调试方式
- 动作：
  1. 新建 `scripts/harness/journey_verify.sh`
  2. 实现 profile 分发机制
  3. 产出统一 JSON/Markdown 摘要
- 产出：
  - `journey_verify.sh`
- 验收：
  1. profile 选择稳定
  2. 输出格式统一
- 当前完成情况：
  1. 已新增 `scripts/harness/journey_verify.sh`
  2. 已支持 `auth/lobby/room/judge-ops/release` 的稳定 profile 分发
  3. 已统一输出 JSON / Markdown 摘要
  4. 当前若缺少可直接消费的运行态证据，会显式标记为 `evidence_missing`
  5. 已补齐 `scripts/harness/tests/test_journey_verify.sh` 回归覆盖

### P3-2 实现 `auth` profile

- 目标：优先覆盖你当前最活跃的认证域。
- 输入：
  - `chat/chat_server/src/handlers/auth.rs`
  - `docs/learning/Restful_Api/008_post_api_auth_v2_sms_send.md`
  - `docs/learning/Restful_Api/009_post_api_auth_v2_signup_phone.md`
- 动作：
  1. 固化认证关键旅程
  2. 支持环境不满足时明确标记为 `evidence_missing` 或 `env_blocked`
  3. 摘要中包含接口、状态、失败原因
- 产出：
  - `auth` runtime profile
- 验收：
  1. 可跑成功/失败样例
  2. 错误归因明确

### P3-3 实现 `lobby` 与 `room` profile

- 目标：覆盖 PRD 主流程。
- 输入：
  - `docs/learning/Restful_Api/019_get_api_debate_topics.md`
  - debate room 相关运行态脚本
- 动作：
  1. 固化 topics / sessions / join
  2. 固化 messages / ws replay / ack 基础路径
  3. 输出日志和关键事件摘要
- 产出：
  - `lobby`
  - `room`
- 验收：
  1. 有最小可复现链路
  2. 能用于模块级回合验收

### P3-4 实现 `judge-ops` 与 `release` profile

- 目标：把运维与发布脚本挂到统一 runtime verify 入口。
- 输入：
  - replay/ops 相关脚本
  - release/preflight/supply-chain 脚本
- 动作：
  1. 对 judge/ops 读路径做统一验证
  2. 对 release 只做聚合，不重写已有门禁语义
- 产出：
  - `judge-ops`
  - `release`
- 验收：
  1. Orchestrator 可按模块自动选择 profile
  2. release profile 可复用现有脚本结果

### P3-5 将 runtime verify 接入 orchestrator 主链

- 目标：让运行态验证成为默认收口动作。
- 输入：
  - `module_turn_harness.sh`
  - `journey_verify.sh`
- 动作：
  1. 增加 `--runtime-profile auto`
  2. 根据改动路径映射 profile
  3. 失败时区分代码问题 / 环境阻塞
- 产出：
  - runtime verify 主链化
- 验收：
  1. 模块级回合默认带运行态验证
  2. 输出证据路径明确

### Phase 3 验收门槛

1. `auth/lobby/room/judge-ops/release` profile 已存在
2. runtime verify 已在 orchestrator 主链
3. 输出统一摘要
4. 环境阻塞和代码失败可区分

---

## 12. Phase 4：CI 分层切换

### P4-1 新建 `pr-fast-gate.yml`

- 目标：降低 PR 反馈时长。
- 输入：
  - 现有 `build.yml`
  - docs lint
  - orchestrator / runtime verify
- 动作：
  1. 抽出路径感知的检查子集
  2. 接入 `harness_docs_lint`
  3. 接入必要的 runtime verify 子集
- 产出：
  - `pr-fast-gate.yml`
- 验收：
  1. PR 反馈时间下降
  2. 失败信息可直接指导修复

### P4-2 新建 `nightly-full-gate.yml`

- 目标：保留全量覆盖。
- 输入：
  - 现有 build 全量逻辑
  - runtime verify profile
- 动作：
  1. 承接全量 Rust gate
  2. 承接全量 frontend smoke/e2e
  3. 承接 docs lint 与 journey verify matrix
  4. 输出统一 artifact
- 产出：
  - `nightly-full-gate.yml`
- 验收：
  1. 夜间可稳定覆盖全量
  2. artifact 目录语义正确

### P4-3 新建 `release-preflight.yml`

- 目标：把发布前门禁独立出来。
- 输入：
  - 现有 preflight/supply-chain/chaos/SBOM 脚本
- 动作：
  1. 只在 tag/release 分支触发
  2. 保持现有门禁语义
  3. 修正默认报告路径
- 产出：
  - `release-preflight.yml`
- 验收：
  1. 发布门禁职责清晰
  2. 报告输出目录统一

### P4-4 退役旧 `build.yml`

- 目标：消除单体式 workflow。
- 输入：
  - 新三层 workflow
- 动作：
  1. 并行运行 1 周
  2. 稳定后退役旧 `build.yml`
  3. 保留变更说明和回滚方案
- 产出：
  - 新主线 CI
- 验收：
  1. 不再由一个 workflow 同时承担三类职责

### Phase 4 验收门槛

1. 三层 workflow 都已存在
2. 报告路径已切换
3. 旧 `build.yml` 已退役或进入退役倒计时

---

## 13. Phase 5：文档治理与持续巡检

### P5-1 建立 explanation/interview 索引

- 目标：把沉淀层变成可消费层。
- 输入：
  - `docs/explanation`
  - `docs/interview`
- 动作：
  1. 新建 README/索引
  2. 分类最近文档
  3. 标记 legacy 与当前主线
- 产出：
  1. `docs/explanation/README.md`
  2. `docs/interview/README.md`
- 验收：
  1. 新人和 agent 都能快速找到相关文档

### P5-2 新建 `doc_gardener.sh`

- 目标：持续回收文档熵增。
- 输入：
  - docs lint
  - 现有历史文档目录
- 动作：
  1. 巡检断链
  2. 巡检过期状态
  3. 巡检 legacy 路径
  4. 巡检无索引归属文档
  5. 输出周报
- 产出：
  - `scripts/quality/doc_gardener.sh`
- 验收：
  1. 每周能稳定生成健康报告
  2. 问题可按类别归档

### P5-3 把 knowledge pack 补写接入周期任务

- 目标：在异步沉淀策略下保持文档质量。
- 输入：
  - explanation/interview skills
  - doc-gardener 报告
- 动作：
  1. 对高价值但缺沉淀的模块补写 explanation/interview
  2. 记录补写来源与触发原因
- 产出：
  - 周期性知识沉淀任务
- 验收：
  1. 重大模块不漏沉淀
  2. 小回合开发不被文档阻塞

### P5-4 扩展质量规则

- 目标：把更多人工约定转成机械约束。
- 输入：
  - 当前质量脚本
  - 架构基线文档
- 动作：
  1. 新增层级依赖检查
  2. 新增关键日志字段检查
  3. 新增命名与禁用模式检查
- 产出：
  - 新的 `scripts/quality/*`
- 验收：
  1. 常见违规可在早期门禁拦截
  2. 误报率可控

### Phase 5 验收门槛

1. explanation/interview 已有索引
2. doc-gardener 已可运行
3. knowledge pack 有异步补写机制
4. 新质量规则已开始接入 fast gate

---

## 14. 阶段依赖关系

依赖顺序固定为：

1. `P1-1/P1-2` -> `P1-5`
2. `P1-3` -> `P2-2/P2-4`
3. `P2-2/P2-3` -> `P3-5`
4. `P1-5 + P3-5` -> `P4-1`
5. `P4-1` -> `P5-4`

禁止倒置的关键关系：

1. 未有活动计划入口与 plan slots 前，不切默认 plan sync 逻辑。
2. 未有 orchestrator 前，不把 runtime verify 视为主链。
3. 未有 docs lint 前，不大规模扩散 doc-gardening。
4. 未完成新三层 workflow 前，不退役旧 `build.yml`。

---

## 15. 里程碑与完成定义

### M1：基础层切换完成

完成定义：

1. `AGENTS.md` TOC 化
2. `docs/harness/` 可用
3. 活动计划入口与 plan slot 生效
4. docs lint 首版可运行
5. 报告默认输出目录已完成语义切分

当前里程碑进度（2026-04-06）：

1. 第 1 项已完成
2. 第 2 项已完成
3. 第 3 项已完成
4. 第 4 项已完成
5. 第 5 项已完成

### M2：单入口编排完成

完成定义：

1. `module-turn-harness` 成为默认入口
2. PRD guard 已改为摘要优先
3. knowledge pack 已脱离主阻塞链
4. 结构化执行日志可输出

### M3：运行态主链完成

完成定义：

1. 关键 runtime profile 已落地
2. Orchestrator 主链带 runtime verify
3. 模块级回合默认输出运行态证据摘要

### M4：CI 主线切换完成

完成定义：

1. 三层 workflow 已上线
2. 旧 build 单体职责已拆开
3. artifact 与报告路径统一

### M5：持续治理上线

完成定义：

1. doc-gardener 已运行
2. explanation/interview 索引完成
3. knowledge pack 周期补写策略生效
4. 质量规则开始持续扩展

---

## 16. 测试与验收计划

### 16.1 Orchestrator 测试

1. `dev` 任务执行链正确
2. `refactor` 任务执行链正确
3. `non-dev` 任务不误触发模块级 hooks
4. `--dry-run` 无副作用
5. `--strict` 遇错即停

### 16.2 Runtime Verify 测试

1. `auth` 成功/失败旅程各 1 组
2. `lobby` 成功/失败旅程各 1 组
3. `room` 成功/失败旅程各 1 组
4. `judge-ops` 成功/失败旅程各 1 组
5. `release` 聚合结果稳定

### 16.3 Docs Lint 测试

1. 空 default slot
2. 悬空 slot 路径
3. 无效状态词
4. 断链
5. legacy 路径残留

### 16.4 CI 测试

1. PR fast gate 只跑必要子集
2. Nightly 跑全量
3. Release preflight 仅在 release/tag 触发

### 16.5 Knowledge Pack 测试

1. 默认小回合不阻塞
2. `force` 可强制触发 explanation/interview
3. 高风险模块 `auto` 可自动命中

---

## 17. 回滚与兼容策略

### 17.1 强切主线的回滚原则

每个阶段都允许回滚到上一层稳定状态，但不保留长期双轨。

### 17.2 分阶段回滚点

1. Phase 1 回滚点：
   - 保留旧 `AGENTS.md` 细则写法
   - 取消活动计划入口与 plan slot 强依赖

2. Phase 2 回滚点：
   - leaf skills 仍可单独执行
   - 但 `module-turn-harness` 入口可暂时降为推荐入口

3. Phase 3 回滚点：
   - runtime verify 可先降为 warning，不阻塞主链

4. Phase 4 回滚点：
   - 新 workflow 并行期间可恢复旧 `build.yml`

5. Phase 5 回滚点：
   - doc-gardener 可暂停，不影响主开发链

### 17.3 不可回滚项

以下一旦完成，不建议回滚：

1. `docs/dev_plan` 与执行证据目录语义切分
2. `AGENTS.md` TOC 化
3. 活动计划入口与 plan slot 引入

---

## 18. 默认约定

1. 本文档是 Harness Engineering 升级的当前主计划文档。
2. 后续执行阶段，默认活动计划入口应由 `.codex/plan-slots/default.txt` 指向 `docs/dev_plan/当前开发计划.md`；并行计划通过命名 slot 管理。
3. 任何新增模块级 skill，若会改变交付链，必须先更新：
   - `docs/harness/20-orchestration.md`
   - `docs/harness/task-flows/`
   - 必要时更新 `module-turn-harness`
   - 本计划文档中的相关阶段说明
4. 任何新增 release/gate/evidence 脚本，默认不得把报告写入 `docs/dev_plan/`。
5. explanation/interview 文档默认不是主阻塞链，但仍是高价值沉淀层，不能直接废弃。

---

## 19. 建议的近期执行顺序

若按最小风险推进，建议从以下顺序开始：

1. `P1-3` 活动计划入口与多计划槽位
2. `P1-5` docs lint 首版
3. `P1-1/P1-2` AGENTS TOC + docs/harness
4. `P2-1/P2-2` module-turn-harness
5. `P2-4` PRD 摘要优先
6. `P3-1/P3-2` runtime verify + auth profile
7. `P4-1` PR fast gate

原因：

1. 活动计划入口/plan slots 和 docs lint 是后续所有变更的稳定锚点。
2. orchestrator 需要建立在目录和规则稳定之后。
3. 认证域是当前最适合作为 runtime verify 首个样板的模块。

### 已完成/未完成矩阵

| 模块 | 优先级 | 状态 | 说明 |
|---|---|---|---|
| module-turn-harness-bootstrap | P1 | 已退役（P2-1/P2-2 历史完成，2026-04-13 已删除） | 曾完成 module-turn-harness skill 与脚本；根据使用反馈已删除该 wrapper，当前默认入口为 task flow 文档，避免开发前误触发 post hooks。 |
| plan-slot-p1-3 | P1 | 进行中（P1-3 已完成） | 已完成 P1-3：default 活动计划入口、命名 slot 解析、单计划/并行计划/收口整合规则已落地。 |
| report-output-p1-4 | P1 | 进行中（P1-4 已完成） | 已完成 P1-4：门禁/预检/验收类默认 Markdown 报告已迁移到 docs/loadtest/evidence，并同步 build.yml 与 README。 |
| harness-docs-lint-p1-5 | P1 | 进行中（P1-5 已完成） | 已新增 harness_docs_lint.sh、回归测试，并将 non-dev 模式接入 docs lint。 |
| harness-structured-logs-p2-3 | P1 | 已退役（P2-3 历史完成，2026-04-13 随 wrapper 删除） | 曾为 module-turn-harness 增加 jsonl 事件日志、summary.json、summary.md；随 wrapper 退役，不再作为当前执行能力。 |
| prd-guard-summary-first-p2-4 | P1 | 进行中（P2-4 已完成） | 已新增 product-goals 摘要文档与独立 PRD guard 脚本；当前通过 task flow 在开发前使用。 |
| knowledge-pack-async-p2-5 | P1 | 进行中（P2-5 已完成） | 已将 explanation/interview 从默认阻塞链移出，并在 orchestrator 中新增 knowledge-pack auto／skip／force。 |

### 下一开发模块建议

1. 评估后续把 knowledge pack auto 从关键词升级为模块注册表
2. 后续为 knowledge pack 增加周期补写机制
3. 不再继续增强或恢复 `module-turn-harness`；如需流程增强，优先增强 task flow 或具体 leaf skill
### 模块完成同步历史

- 2026-04-06：推进 `module-turn-harness-bootstrap`；实现 module-turn-harness skill 与统一模块级入口脚本，并同步 AGENTS 与 harness 文档
- 2026-04-06：推进 `plan-slot-p1-3`；实现 P1-3 活动计划入口与多计划槽位，并同步 docs/harness 使用规则
- 2026-04-06：推进 `report-output-p1-4`；实现 P1-4 计划/证据目录职责切分，迁移默认报告输出并同步 CI 与文档
- 2026-04-06：推进 `harness-docs-lint-p1-5`；实现 P1-5 docs lint 首版并接入 non-dev 轻量模式
- 2026-04-06：推进 `harness-structured-logs-p2-3`；实现 P2-3 结构化执行日志与 harness run summary
- 2026-04-06：推进 `prd-guard-summary-first-p2-4`；实现 P2-4 PRD guard 摘要优先与高风险全文兜底
- 2026-04-06：推进 `knowledge-pack-async-p2-5`；实现 P2-5 knowledge pack 异步化与 auto skip/force 策略
- 2026-04-13：推进 `task-flow-lifecycle-correction`；根据使用反馈将日常默认入口从 `module-turn-harness` 强编排调整为 `docs/harness/task-flows/`，并彻底删除 `module-turn-harness` wrapper，避免开发前误触发 test guard、commit message、plan sync 等 post hooks
