# EchoIsle Harness Engineering 使用教程

更新时间：2026-04-13
状态：基于 task flow 的当前使用手册

---

## 1. 这份教程解决什么问题

这份文档说明 EchoIsle 当前如何使用 Codex、skills 和 harness 文档。

当前原则是：

1. `AGENTS.md` 只做导航和硬规则入口
2. `docs/harness/task-flows/` 承担具体任务流程
3. skills 保持独立能力，由任务生命周期决定什么时候触发
4. `module-turn-harness` 保留为可选包装工具，不再是普通开发任务的默认开工动作

---

## 2. 正确心智

当前 EchoIsle harness 是“任务流程说明 + skill 工具箱 + 少量硬规则”，不是强制自动驾驶编排器。

你可以把它理解成 4 层：

1. 规则层
   - `AGENTS.md`
   - `docs/harness/*.md`

2. 任务流程层
   - `docs/harness/task-flows/dev.md`
   - `docs/harness/task-flows/refactor.md`
   - `docs/harness/task-flows/non-dev.md`
   - `docs/harness/task-flows/stage-closure.md`

3. 计划层
   - `docs/dev_plan/当前开发计划.md`
   - `docs/dev_plan/todo.md`
   - `docs/dev_plan/completed.md`
   - `.codex/plan-slots/*.txt`

4. 验证与证据层
   - `scripts/quality/harness_docs_lint.sh`
   - `scripts/harness/journey_verify.sh`
   - `artifacts/harness/`
   - `docs/loadtest/evidence/`

一句话记忆：

先判定任务类型，再读对应 task flow，按生命周期触发 skill。

---

## 3. 日常最短路径

### 3.1 和 Codex 对话时

通常你不需要自己手敲脚本。

你可以直接说明任务类型和 slot：

1. `这是一个 dev 任务，slot backend-signin。请先读取 dev task flow，开发前只做 PRD 对齐，不要提前触发 post hooks。代码完成后再执行测试、commit message 和计划回写。`
2. `这是一个 refactor 任务，slot auth-session。请先读取 refactor task flow，代码完成后再做 optimization plan sync。`
3. `这是一个 non-dev 任务，请读取 non-dev task flow，只在文档结构变更后跑 docs lint。`
4. `这是阶段收口任务，请读取 stage-closure task flow，把完成项写入 completed，把延后技术债写入 todo，然后清空活动计划。`

### 3.2 什么时候手动执行脚本

手动执行脚本只在你明确需要时使用：

1. 想跑 docs lint：

```bash
bash /Users/panyihang/Documents/EchoIsle/scripts/quality/harness_docs_lint.sh \
  --root /Users/panyihang/Documents/EchoIsle
```

2. 想看运行态验证摘要：

```bash
bash /Users/panyihang/Documents/EchoIsle/scripts/harness/journey_verify.sh \
  --profile auth \
  --emit-json /Users/panyihang/Documents/EchoIsle/artifacts/harness/manual-auth.summary.json \
  --emit-md /Users/panyihang/Documents/EchoIsle/artifacts/harness/manual-auth.summary.md
```

3. 想明确预览完整 harness hook 链：

```bash
bash /Users/panyihang/Documents/EchoIsle/scripts/harness/module_turn_harness.sh \
  --task-kind dev \
  --module "auth-session-hardening" \
  --summary "加固 auth session revoke 一致性与回收链路" \
  --dry-run
```

注意：第 3 类不是普通 dev/refactor 开工前默认动作。

---

## 4. 什么时候看什么入口

### 4.1 `AGENTS.md`

用途：

1. 看当前硬规则
2. 找到任务流程文档入口
3. 找到 `docs/harness/` 和 `docs/architecture/README.md`

不适合：

1. 不适合当完整 skill registry
2. 不适合当详细架构文档
3. 不适合当开发计划正文
4. 不适合手动推断完整 pre/post hook 链

### 4.2 `docs/harness/task-flows`

用途：

1. `dev.md`：功能开发和行为变更
2. `refactor.md`：结构优化和性能优化
3. `non-dev.md`：文档、分析、评审、规划
4. `stage-closure.md`：活动计划阶段收口

### 4.3 `docs/architecture/README.md`

用途：

1. 快速定位代码
2. 先知道该看后端、前端、AI 服务还是 harness
3. 减少一上来就扫描整个仓库的 token 消耗

### 4.4 `module-turn-harness`

用途：

1. 用户明确要求 `module-turn-harness`
2. 用户明确要求 `harness dry-run`
3. 用户明确要求完整 hook 链路预览
4. 调试 harness 自身
5. 手动验证 hook 顺序或 artifact 输出

不适合：

1. 普通 dev/refactor 写代码前的默认动作
2. 代码尚未改完时运行 post hooks
3. 只需要 PRD 对齐的开发前阶段

### 4.5 `journey_verify`

用途：

1. 生成统一运行态验证摘要
2. 按 `auth/lobby/room/judge-ops/release` profile 查看证据
3. 明确区分 `pass/fail/env_blocked/evidence_missing`

当前边界：

1. 它还不会自动覆盖所有真实业务旅程
2. 它还没有接入普通开发主链
3. 它当前是统一入口，不是完整运行态系统

---

## 5. 三种任务类型怎么用

### 5.1 `dev`

用于：

1. 新功能
2. 行为改变的 bug fix
3. 新接口 / 新逻辑 / 新流程

生命周期：

1. 开发前：读取 `task-flows/dev.md`，做 PRD/product-goals 对齐，必要时写活动计划。
2. 开发中：实现代码，遵守注释、兼容性、API 跨层同步等硬规则。
3. 开发后：再触发 test guard、commit message、plan sync，必要时补 knowledge pack。

### 5.2 `refactor`

用于：

1. 结构优化
2. 可维护性提升
3. 性能优化
4. 不以新增产品能力为主目标的代码整理

生命周期：

1. 开发前：读取 `task-flows/refactor.md`，确认边界和 PRD/product-goals 对齐。
2. 开发中：保持外部行为不变；如果行为改变，重新归类为 `dev`。
3. 开发后：再触发 test guard、commit message、optimization plan sync，必要时补 knowledge pack。

### 5.3 `non-dev`

用于：

1. 纯文档调整
2. 规则同步
3. 分析/评审/规划
4. prompt 草拟

生命周期：

1. 读取 `task-flows/non-dev.md`。
2. 默认不触发模块级 pre/post hooks。
3. 文档结构变更后，可运行 docs lint。

---

## 6. `plan` 和 `slot` 怎么用

### 6.1 `--plan`

意思是直接指定“写这个文件”。

适合：

1. 这轮明确要写某一份计划文档
2. 不想经过 slot 解析
3. 特殊一次性文档

### 6.2 `--slot`

意思是指定“这轮属于哪个活动计划槽位”。

`slot` 不是文档内容本身，而是一个命名工作位，最终通过 `.codex/plan-slots/<slot>.txt` 指向实际文档。

示例：

1. `backend-signin`
2. `frontend-ui`
3. `AI_module`

### 6.3 单计划

如果当前只有一个短期计划：

1. 默认可使用 `default`
2. `default` 指向 `docs/dev_plan/当前开发计划.md`
3. 通常不必显式传 `--slot`

### 6.4 并行计划

如果同时推进多个计划：

1. 每个线程必须有独立 `slot`
2. 每个线程只能写自己的活动计划
3. 不要让多个线程共用 `default`

### 6.5 阶段收口

当你觉得“这轮先到这里”时：

1. 读取 `task-flows/stage-closure.md`
2. 把主体已完成内容整合进 `docs/dev_plan/completed.md`
3. 把延后技术债/收口债整合进 `docs/dev_plan/todo.md`
4. 清空、重置或归档活动计划文档
5. 必要时回收或重绑对应 `slot`

---

## 7. 当前文档职责

### 7.1 `docs/dev_plan`

放：

1. 当前计划
2. 长期技术债
3. 已完成沉淀

当前更准确的分工是：

1. `当前开发计划.md`
   - 只放这轮过程
   - 可写完整计划、执行矩阵、过程回写
2. `completed.md`
   - 只放主体已完成模块快照
   - 不写大段开发过程
   - 如仍有后续债务，用“关联待办”指向 `todo.md`
3. `todo.md`
   - 只放明确延后的技术债/收口债
   - 不放新需求脑暴或模糊 wishlist

不要默认再往 `docs/dev_plan` 放：

1. 新验收报告
2. 新门禁报告
3. 新预检报告

### 7.2 `docs/explanation`

是深入讲解沉淀层。

当前不是每一轮都必须生成，也不是主决策入口。

### 7.3 `docs/interview`

是开发与排障沉淀层。

当前不是每个小修都必须阻塞生成。

### 7.4 `docs/harness`

是当前 harness 规则层。

如果你想知道“现在到底该怎么做”，优先看 task flow，而不是历史讲解文档。

---

## 8. 推荐工作流

### 8.1 新开普通开发任务

1. 和 Codex 说明需求、任务类型、slot。
2. Codex 读取对应 task flow。
3. 开发前只做 PRD/product-goals 对齐和计划准备。
4. Codex 写代码。
5. 代码完成后再跑测试、commit message、计划回写。
6. 如需要，再看 `journey_verify`。

### 8.2 同时推进两个任务

1. 给两个线程分配不同 `slot`。
2. 每个线程只维护自己的活动计划文档。
3. 不要让两个线程共用 `default`。
4. 阶段结束后分别收口进 `todo.md` / `completed.md`。

### 8.3 阶段收口

当你觉得“这轮先到这里”时，推荐固定按下面 4 步做：

1. 把当前活动计划里“主体已落地”的内容写入 `completed.md`。
2. 把当前活动计划里“明确延后”的技术债写入 `todo.md`。
3. 在 `completed.md` 中给每条完成项补 `归档来源`。
4. 清空、重置或归档活动计划文档。

可以直接这样对 Codex 说：

`把当前开发计划按阶段收口规范整合：主体已完成内容写入 completed，延后收口的技术债写入 todo，然后清空当前开发计划。`

### 8.4 文档和规则治理

1. 读取 `task-flows/non-dev.md`。
2. 修改文档。
3. 如涉及 harness/计划文档结构，运行 `harness_docs_lint.sh`。

### 8.5 运行态验证

1. 直接运行 `journey_verify.sh`。
2. 明确指定 `profile`。
3. 看 `.journey.md`。

---

## 9. 推荐对 Codex 的说法

### 9.1 单计划开发

`这是一个 dev 任务，slot default，模块是 auth-session-hardening。请先读取 dev task flow，开发前只做 PRD/product-goals 对齐并更新当前活动计划；不要提前触发 post hooks。代码完成后再执行测试、commit message 和计划回写。`

### 9.2 并行计划开发

`为 slot AI_module 生成后端 AI 模块开发计划，写入该 slot 对应文档；后续执行和回写都只使用这个 slot。请按 dev task flow 执行。`

### 9.3 阶段收口

`把 slot AI_module 当前计划按 stage-closure task flow 收口：主体已完成内容写入 completed.md，延后收口的技术债写入 todo.md，然后清空或归档该活动计划。`

### 9.4 文档治理

`这是一个 non-dev 任务，请读取 non-dev task flow；只在文档结构变更后跑 docs lint。`

### 9.5 运行态验证

`帮我用 journey_verify 跑 auth profile，并输出 JSON 和 Markdown 摘要。`

### 9.6 明确要跑 harness wrapper

`我明确要求使用 module-turn-harness 做一次 dry-run，预览完整 hook 链路。`

---

## 10. 当前边界

当前已经能用，但不要误会成这些也已经完成：

1. `module-turn-harness` 不再是普通 dev/refactor 的默认开工动作。
2. `journey_verify` 还没有接入普通开发主链。
3. `auth/lobby/room/judge-ops/release` 目前是统一入口 + 摘要框架，不是全部都已细化完成。
4. CI 三层拆分还没完成。
5. knowledge pack 周期补写还没完成。

---

## 11. 一页总结

日常最实用的用法只有 5 条：

1. 规则先看 `AGENTS.md`，找代码先看 `docs/architecture/README.md`。
2. 命中任务类型后，先读 `docs/harness/task-flows/` 对应文档。
3. 开发前只做 pre hooks，开发后才做 post hooks。
4. 单计划用 `default`，并行计划用独立 `slot`。
5. `module-turn-harness` 是可选包装工具，不是默认开发前置动作。

如果只记一句话：

先判定任务类型，再读 task flow，最后按生命周期触发 skill。

