# EchoIsle Harness Engineering 使用教程

更新时间：2026-04-07
状态：基于当前已完成模块的实际使用手册

---

## 1. 这份教程解决什么问题

这份文档只讲一件事：

在 EchoIsle 当前已经落地的 Harness Engineering 状态下，你日常该如何正确使用 Codex。

它不讲未来规划，不讲未落地能力，只讲当前已经能用的内容：

1. `AGENTS.md` 规则入口
2. `docs/harness/` 规则主目录
3. `module-turn-harness` 模块级统一入口
4. `slot` / `plan` 活动计划机制
5. `docs lint`
6. `journey_verify` 统一运行态验证入口
7. 当前文档、证据、knowledge pack 的职责

---

## 2. 先建立正确心智

当前 EchoIsle 的 harness，不是“自动替你做完所有工程管理”的平台，而是一个已经可用的轻量工程骨架。

你可以把它理解成 4 层：

1. 规则层
   - `AGENTS.md`
   - `docs/harness/*.md`

2. 计划层
   - `docs/dev_plan/当前开发计划.md`
   - `docs/dev_plan/todo.md`
   - `docs/dev_plan/completed.md`
   - `.codex/plan-slots/*.txt`

3. 执行层
   - `scripts/harness/module_turn_harness.sh`

4. 验证与证据层
   - `scripts/quality/harness_docs_lint.sh`
   - `scripts/harness/journey_verify.sh`
   - `artifacts/harness/`
   - `docs/loadtest/evidence/`

一句话记忆：

先看规则，明确计划，再走统一入口，最后看证据。

---

## 3. 日常使用的最短路径

### 3.1 如果你正在和 Codex 对话

通常你不需要自己手敲脚本。

你只需要把任务说清楚，Codex 应该替你完成：

1. 识别任务类型
2. 生成或更新活动计划
3. 走 `module-turn-harness`
4. 回写计划
5. 必要时补 explanation / interview
6. 输出测试与证据结论

你可以直接这样说：

1. `这是一个 dev 任务，为 slot backend-signin 生成计划并执行，先 dry-run。`
2. `这是一个 refactor 任务，模块是 auth-session-hardening，按统一入口执行。`
3. `这是一个 non-dev 任务，先跑 docs lint。`

### 3.2 如果你想自己在终端里显式执行

最常用的命令是：

```bash
bash /Users/panyihang/Documents/EchoIsle/scripts/harness/module_turn_harness.sh \
  --task-kind dev \
  --module "auth-session-hardening" \
  --summary "加固 auth session revoke 一致性与回收链路" \
  --dry-run
```

和：

```bash
bash /Users/panyihang/Documents/EchoIsle/scripts/harness/journey_verify.sh \
  --profile auth \
  --emit-json /Users/panyihang/Documents/EchoIsle/artifacts/harness/manual-auth.summary.json \
  --emit-md /Users/panyihang/Documents/EchoIsle/artifacts/harness/manual-auth.summary.md
```

---

## 4. 什么时候用什么入口

### 4.1 `AGENTS.md`

用途：

1. 看当前有哪些 skill
2. 看当前有哪些强制规则
3. 确认默认入口是不是 `module-turn-harness`

不适合做什么：

1. 不适合当项目目录树
2. 不适合当详细架构文档
3. 不适合当开发计划正文

### 4.2 `docs/architecture/README.md`

用途：

1. 快速定位代码
2. 先知道该看后端、前端、AI 服务还是 harness
3. 减少一上来就扫描整个仓库的 token 消耗

### 4.3 `module-turn-harness`

适合：

1. 模块级功能开发
2. 模块级行为修复
3. 模块级重构/优化
4. 文档/规则类轻量检查

不适合：

1. 纯闲聊
2. 纯方案脑暴
3. 不改任何仓库内容的纯分析问答

### 4.4 `journey_verify`

适合：

1. 你想要统一的运行态验证摘要
2. 你想按 `auth/lobby/room/judge-ops/release` 视角看当前验证结论
3. 你想把专项脚本、smoke、证据缺口统一收束成一个结论文件

当前不适合期待：

1. 它还不会自动覆盖所有真实业务旅程
2. 它还没有接入 `module-turn-harness` 主链
3. 它当前是统一入口，不是完整运行态系统

---

## 5. 三种任务类型怎么用

### 5.1 `dev`

用于：

1. 新功能
2. 行为改变的 bug fix
3. 新接口 / 新逻辑 / 新流程

当前执行链：

1. PRD gate
2. test guard
3. commit message 建议
4. plan sync
5. knowledge pack 决策
6. 按策略触发 interview / explanation

示例：

```bash
bash /Users/panyihang/Documents/EchoIsle/scripts/harness/module_turn_harness.sh \
  --task-kind dev \
  --slot "AI_module" \
  --module "backend-ai-module" \
  --summary "实现后端 AI 模块新判决链路" \
  --knowledge-pack auto \
  --dry-run
```

### 5.2 `refactor`

用于：

1. 结构优化
2. 可维护性提升
3. 性能优化
4. 不以新增产品能力为主目标的代码整理

当前执行链：

1. PRD gate
2. test guard
3. commit message 建议
4. optimization plan sync
5. knowledge pack 决策
6. 按策略触发 interview / explanation

### 5.3 `non-dev`

用于：

1. 纯文档调整
2. 规则同步
3. harness 文档更新
4. 轻量结构检查

当前最常见用途：

1. 跑 `harness_docs_lint`
2. 做 harness 文档收口

示例：

```bash
bash /Users/panyihang/Documents/EchoIsle/scripts/harness/module_turn_harness.sh \
  --task-kind non-dev \
  --module "docs-governance-check" \
  --summary "检查当前计划与 harness 文档结构"
```

---

## 6. `plan` 和 `slot` 到底怎么用

### 6.1 `--plan`

意思是：

直接指定“写这个文件”。

适合：

1. 这轮你非常明确要写某一份计划文档
2. 你不想经过 slot 解析
3. 你在做特殊一次性文档

### 6.2 `--slot`

意思是：

指定“这轮属于哪个活动计划槽位”。

`slot` 不是文档内容本身，而是一个命名工作位。

例如：

1. `backend-signin`
2. `frontend-ui`
3. `AI_module`

它最终会通过 `.codex/plan-slots/<slot>.txt` 指向某一份实际文档。

### 6.3 单计划怎么用

如果你当前只有一个短期计划：

1. 默认走 `default`
2. `default` 指向 `docs/dev_plan/当前开发计划.md`
3. 通常不必显式传 `--slot`

### 6.4 并行计划怎么用

如果你同时推进多个计划：

1. 每个线程必须有独立 `slot`
2. 每个线程只能写自己的活动计划
3. 不要让多个线程共用 `default`

示例：

后端线程：

```bash
bash /Users/panyihang/Documents/EchoIsle/scripts/harness/module_turn_harness.sh \
  --task-kind refactor \
  --slot "backend-signin" \
  --module "post-api-signin-flow-optimization" \
  --summary "优化 POST /api/auth/v2/signin 流程与鉴权链路"
```

前端线程：

```bash
bash /Users/panyihang/Documents/EchoIsle/scripts/harness/module_turn_harness.sh \
  --task-kind dev \
  --slot "frontend-ui" \
  --module "frontend-ui-polish" \
  --summary "优化前端 UI 结构与交互表现"
```

### 6.5 阶段收口怎么用

当你觉得“这轮先到这里”时：

1. 把该活动计划中已完成内容整合进 `docs/dev_plan/completed.md`
2. 把未完成但后续要继续的内容整合进 `docs/dev_plan/todo.md`
3. 清空、重置或归档该活动计划文档
4. 必要时回收或重绑对应 `slot`

---

## 7. 常用参数怎么理解

### 7.1 `--dry-run`

作用：

1. 只看会执行什么
2. 不真正执行完整链路
3. 非常适合开工前确认

建议：

1. 新任务先 `dry-run`
2. 并行计划首次绑定 slot 时先 `dry-run`

### 7.2 `--strict`

作用：

1. 任一步失败立即停
2. 适合关键回合

### 7.3 `--prd-mode auto|summary|full`

当前默认是 `auto`。

含义：

1. `summary`
   - 默认先读 `docs/harness/product-goals.md`

2. `full`
   - 强制回读完整 PRD

3. `auto`
   - 普通任务先走摘要
   - 高风险任务自动回读完整 PRD

### 7.4 `--knowledge-pack auto|skip|force`

当前默认是 `auto`。

含义：

1. `auto`
   - 普通小回合默认不阻塞
   - 高价值或高风险回合自动补写 explanation/interview

2. `skip`
   - 本轮显式跳过 explanation/interview

3. `force`
   - 本轮显式强制补写 explanation/interview

---

## 8. 执行后去哪里看结果

### 8.1 `module-turn-harness`

每次执行后，重点看：

1. `artifacts/harness/<run>.jsonl`
2. `artifacts/harness/<run>.summary.json`
3. `artifacts/harness/<run>.summary.md`

它们分别适合：

1. `jsonl`
   - 看每一步执行事件

2. `summary.json`
   - 机器可读

3. `summary.md`
   - 人类快速看结果

### 8.2 `journey_verify`

每次执行后，重点看：

1. `*.journey.json`
2. `*.journey.md`

如果当前 profile 还没有真实证据，看到 `evidence_missing` 是正常的。
它表示：

1. profile 已建立
2. 摘要已统一
3. 但具体验证旅程还没完全落地

### 8.3 报告类证据

当前默认应优先去这些目录找：

1. `docs/loadtest/evidence`
2. `docs/consistency_reports`

`docs/dev_plan` 不再是新增执行报告的首选默认目录。

---

## 9. 当前文档职责怎么分

### 9.1 `docs/dev_plan`

放：

1. 当前计划
2. 长期待办
3. 已完成沉淀

不要默认再往里面放：

1. 新验收报告
2. 新门禁报告
3. 新预检报告

### 9.2 `docs/explanation`

是深入讲解沉淀层。

当前不是：

1. 每一轮都必须生成
2. 当前主决策入口

### 9.3 `docs/interview`

是开发与排障沉淀层。

当前不是：

1. 每个小修都必须阻塞生成

### 9.4 `docs/harness`

是当前 harness 规则层。

如果你想知道“现在到底该怎么做”，优先看这里，而不是看历史讲解文档。

---

## 10. 当前推荐工作流

### 10.1 新开一个普通开发任务

1. 和 Codex 说明需求
2. 让 Codex 生成短期计划并写入活动计划文档
3. 先 `dry-run`
4. 确认无误后正式执行
5. 看 `artifacts/harness/*.summary.md`
6. 如需要，再看 `journey_verify`

### 10.2 同时推进两个任务

1. 给两个线程分配不同 `slot`
2. 每个线程只维护自己的活动计划文档
3. 不要让两个线程共用 `default`
4. 阶段结束后分别收口进 `todo.md` / `completed.md`

### 10.3 做文档和规则治理

1. 直接用 `non-dev`
2. 或直接跑 `harness_docs_lint.sh`

### 10.4 想看当前运行态验证有没有统一出口

1. 直接跑 `journey_verify.sh`
2. 明确指定 `profile`
3. 看 `.journey.md`

---

## 11. 推荐对 Codex 的说法

### 11.1 单计划开发

你可以这样说：

`这是一个 dev 任务，模块是 auth-session-hardening，先生成计划并写入当前开发计划，然后按统一入口 dry-run。`

### 11.2 并行计划开发

你可以这样说：

`为 slot AI_module 生成后端 AI 模块开发计划，写入该 slot 对应文档；后续执行和回写都只使用这个 slot。`

### 11.3 阶段收口

你可以这样说：

`把 slot AI_module 当前计划里已完成内容整合进 completed.md，未完成内容整合进 todo.md，然后清空或归档该活动计划。`

### 11.4 文档治理

你可以这样说：

`这是一个 non-dev 任务，先跑 docs lint，再同步 harness 文档。`

### 11.5 运行态验证

你可以这样说：

`帮我用 journey_verify 跑 auth profile，并输出 JSON 和 Markdown 摘要。`

---

## 12. 当前边界，不要误用

当前已经能用，但不要误会成这些也已经完成：

1. `journey_verify` 还没有接入 `module-turn-harness` 主链
2. `auth/lobby/room/judge-ops/release` 目前是统一入口 + 摘要框架，不是全部都已细化完成
3. CI 三层拆分还没完成
4. knowledge pack 周期补写还没完成
5. docs lint 还没全量接入 CI

所以当前正确认知是：

1. 这套 harness 已经足够日常使用
2. 但它仍然是“可用的工程骨架”，不是最终自动化平台

---

## 13. 一页总结

日常最实用的用法只有 5 条：

1. 规则先看 `AGENTS.md`，找代码先看 `docs/architecture/README.md`
2. 模块级任务默认走 `module-turn-harness`
3. 单计划用 `default`，并行计划用独立 `slot`
4. 开发中回写活动计划，阶段结束再整理进 `todo.md` / `completed.md`
5. 想要统一运行态结论时，用 `journey_verify.sh`

如果只记一句话：

先定计划槽位，再走统一入口，最后看 artifact 和验证摘要。
