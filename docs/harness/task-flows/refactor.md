# Refactor Task Flow

更新时间：2026-04-13
状态：当前默认 refactor/optimization 流程

---

## 1. 适用场景

满足以下特征时按 `refactor` 处理：

1. 主要目标是结构优化、可读性、可维护性或性能
2. 不是以新增产品能力为主
3. 原则上不改变外部行为

如果引入新行为或改变外部行为，优先按 `dev` 处理。

---

## 2. 开发前

开发前只做必要的理解、计划和 pre hooks：

1. 明确重构边界、目标模块和活动计划 `slot` / `plan`。
2. 执行或读取 PRD/product-goals 对齐；可使用 `pre-module-prd-goal-guard`。
3. 确认不引入为未发布能力服务的长期兼容层、adapter shim、双轨逻辑。
4. 确认如果涉及 API/DTO/WS payload，需要同步检查跨层调用方。

开发前不要触发 post hooks：

1. 不跑 `post-module-test-guard` 的完整测试门禁。
2. 不生成最终 commit message。
3. 不执行 `post-optimization-plan-sync`。
4. 不触发 explanation/interview 补写。

---

## 3. 开发中

开发中按仓库规则实现：

1. 保持外部行为不变，除非用户明确要求改变行为。
2. 遇到一致性、事务、并发、幂等、时序或复杂分支时补精简中文注释。
3. 如果发现重构需要改变外部行为，暂停并把任务重新归类为 `dev`。
4. 尽量一次性切主链并清理旧路径，不留下无限期 fallback。

---

## 4. 开发后

代码实现完成后，再按需要触发 post hooks：

1. 使用 `post-module-test-guard` 检查测试变更并运行合适的测试门禁。
2. 使用 `post-module-commit-message` 在终端/对话中输出 commit message 推荐。
3. 使用 `post-optimization-plan-sync` 回写优化计划或优化矩阵。
4. 仅在高价值或用户明确要求时补写 explanation/interview。

---

## 5. 可选工具

`module-turn-harness` 只在以下场景使用：

1. 用户明确要求 `module-turn-harness`。
2. 用户明确要求 `harness dry-run` 或完整 hook 链路预览。
3. 正在调试 harness 自身。
4. 需要手动验证 hook 顺序。

不要把 `module-turn-harness --task-kind refactor` 当成普通 refactor 任务的写代码前默认动作。

