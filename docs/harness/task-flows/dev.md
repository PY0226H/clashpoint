# Dev Task Flow

更新时间：2026-04-27
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

## 3. 开发后

代码实现完成后，再按需要触发 post hooks：

1. 先做代码地图漂移检查：如果改动影响子系统划分、主入口、模块边界、跨层调用路径、workspace/package 成员、主要页面/handler/service/domain 位置，更新 `docs/architecture/README.md`。
2. 只有影响“第一跳定位”的变化才更新代码地图；局部函数实现、算法细节、测试细节、临时脚本变化通常不更新。
3. 更新代码地图时保持轻量，不展开成完整架构说明。
4. 使用 `post-module-test-guard` 检查测试变更并运行合适的测试门禁。
5. 使用 `post-module-commit-message` 在终端/对话中输出 commit message 推荐。
6. 使用 `post-module-plan-sync` 回写当前活动计划。
7. 仅在高价值或用户明确要求时补写 explanation/interview。
8. 如果需要统一运行态验证，再单独使用 `journey_verify.sh`。
9. 最终回复说明代码地图是否已更新；若未更新，简述“不影响第一跳定位”的判断依据。
