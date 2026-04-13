# Dev Task Flow

更新时间：2026-04-13
状态：当前默认 dev 流程

---

## 1. 适用场景

满足任一情况即可按 `dev` 处理：

1. 新增功能
2. 修复外部可见行为
3. 修改业务逻辑
4. 新增或修改接口、schema、数据流
5. 其它会改变模块对外行为的改动

---

## 2. 开发前

开发前只做必要的理解、计划和 pre hooks：

1. 明确用户需求、模块范围、活动计划 `slot` / `plan`。
2. 必要时生成或更新当前活动计划文档，不写入 `todo.md` / `completed.md`。
3. 执行或读取 PRD/product-goals 对齐；可使用 `pre-module-prd-goal-guard`。
4. 命中高风险产品边界时，回读权威 PRD。

开发前不要触发 post hooks：

1. 不跑 `post-module-test-guard` 的完整测试门禁。
2. 不生成最终 commit message。
3. 不执行 `post-module-plan-sync`。
4. 不触发 explanation/interview 补写。

---

## 3. 开发中

开发中按仓库规则实现：

1. 先用 `docs/architecture/README.md` 定位代码。
2. 修改后端、API 契约、前端主流程时，遵守 `AGENTS.md` 对应规则。
3. 对 Redis/DB 一致性、事务补偿、并发/锁、幂等、防重、复杂分支补精简中文注释。
4. EchoIsle 尚未上线，默认直接切主链并清理旧路径，不为未发布能力保留长期兼容层。

---

## 4. 开发后

代码实现完成后，再按需要触发 post hooks：

1. 使用 `post-module-test-guard` 检查测试变更并运行合适的测试门禁。
2. 使用 `post-module-commit-message` 在终端/对话中输出 commit message 推荐。
3. 使用 `post-module-plan-sync` 回写当前活动计划。
4. 仅在高价值或用户明确要求时补写 explanation/interview。
5. 如果需要统一运行态验证，再单独使用 `journey_verify.sh`。

---

## 5. 可选工具

`module-turn-harness` 只在以下场景使用：

1. 用户明确要求 `module-turn-harness`。
2. 用户明确要求 `harness dry-run` 或完整 hook 链路预览。
3. 正在调试 harness 自身。
4. 需要手动验证 hook 顺序。

不要把 `module-turn-harness --task-kind dev` 当成普通 dev 任务的写代码前默认动作。

