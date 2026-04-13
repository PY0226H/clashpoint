# EchoIsle Orchestration

更新时间：2026-04-13
状态：可选编排工具说明

---

## 1. 当前事实

EchoIsle 当前的日常默认入口已经调整为任务流程文档：

1. `docs/harness/task-flows/dev.md`
2. `docs/harness/task-flows/refactor.md`
3. `docs/harness/task-flows/non-dev.md`
4. `docs/harness/task-flows/stage-closure.md`

`module-turn-harness` 仍然存在：

1. `skills/module-turn-harness/SKILL.md`
2. `scripts/harness/module_turn_harness.sh`

但它现在是可选包装工具，不是普通 dev/refactor 任务写代码前的默认动作。

---

## 2. 为什么降级为可选工具

`module-turn-harness` 当前会串联 pre/post hooks：

1. PRD gate
2. test guard
3. commit message 推荐
4. plan sync / optimization plan sync
5. knowledge pack 决策

这条链路适合完整链路预览或手动收口，但不适合在代码尚未修改前默认执行。

原因：

1. `post-module-test-guard` 应在代码改完后执行。
2. `post-module-commit-message` 应在有真实改动后输出。
3. `post-module-plan-sync` / `post-optimization-plan-sync` 应在阶段结果明确后回写。
4. explanation/interview 不应阻塞普通小回合。

因此日常工作应先读取 task flow，并按开发前、开发中、开发后分阶段触发 skill。

---

## 3. 什么时候使用 `module-turn-harness`

只在以下情况默认使用：

1. 用户明确要求 `module-turn-harness`
2. 用户明确要求 `harness dry-run`
3. 用户明确要求完整 hook 链路预览
4. 正在调试 harness 自身
5. 需要手动验证 hook 顺序或 artifact 输出

不要在普通 dev/refactor 开工前自动运行：

```bash
bash scripts/harness/module_turn_harness.sh --task-kind dev ...
```

除非用户明确要求。

---

## 4. 日常生命周期

### 4.1 `dev`

默认读 `docs/harness/task-flows/dev.md`。

生命周期：

1. 开发前：PRD/product-goals 对齐，必要时更新活动计划。
2. 开发中：按代码地图实现，遵守硬规则。
3. 开发后：测试门禁、commit message 推荐、计划回写、必要时 knowledge pack。

### 4.2 `refactor`

默认读 `docs/harness/task-flows/refactor.md`。

生命周期：

1. 开发前：确认重构边界、PRD/product-goals 对齐、兼容层策略。
2. 开发中：保持外部行为不变，必要时补注释。
3. 开发后：测试门禁、commit message 推荐、优化计划回写、必要时 knowledge pack。

### 4.3 `non-dev`

默认读 `docs/harness/task-flows/non-dev.md`。

生命周期：

1. 默认不触发模块级 pre/post hooks。
2. 修改 harness/计划文档结构后，可运行 docs lint。
3. 用户明确点名某个 skill 时，再按 skill 说明执行。

### 4.4 `stage-closure`

默认读 `docs/harness/task-flows/stage-closure.md`。

生命周期：

1. 已完成内容进入 `completed.md`。
2. 延后技术债进入 `todo.md`。
3. 活动计划清空、重置或归档。
4. 必要时运行 docs lint。

---

## 5. `slot` / `plan` 仍然保留

`slot` / `plan` 机制仍然有效，但不再绑定 `module-turn-harness` 默认执行。

使用原则：

1. 单计划时期可使用 `default` slot。
2. 并行计划时期每个线程使用独立 `slot`。
3. 开发中回写活动计划。
4. 阶段收口时再整理进 `todo.md` / `completed.md`。

---

## 6. 当前限制

1. `module-turn-harness` 仍会串联 pre/post hooks，因此不要把它作为普通开发前置动作。
2. `journey_verify.sh` 已是统一运行态验证入口，但尚未接入普通开发主链。
3. harness artifact 记录的是脚本执行过程，不替代代码评审、测试结论或 runtime verify。
4. knowledge pack 的 auto 判定仍是启发式，不是模块注册表。

